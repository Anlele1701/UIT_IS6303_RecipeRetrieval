# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2", "numpy>=1.26", "tokenizers>=0.19"]
# ///
"""Load Shengtao/recipe into ParadeDB, then build Chunking strategies from it.

    uv run scripts/ingest.py load                # CSV -> source tables; refused while strategies exist
    uv run scripts/ingest.py chunk <name>        # build one strategy end to end, index included
    uv run scripts/ingest.py drop <name> [--yes] # remove a strategy; a loaded one needs --yes

A crashed `chunk` is cleaned up by running it again. Strategies are defined in STRATEGIES.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "recipe.csv"
CSV_URL = "https://huggingface.co/datasets/Shengtao/recipe/resolve/main/recipe.csv"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5434/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
EMBED_BATCH = 256

BATCH_SIZE = 200  # Recipes per load transaction

NUTRITION = {  # source column -> recipe_nutrition column
    "calories": "calories", "calories_from_fat": "calories_from_fat", "fat_g": "fat_g",
    "saturated_fat_g": "saturated_fat_g", "carbohydrates_g": "carbohydrates_g",
    "sugars_g": "sugars_g", "dietary_fiber_g": "dietary_fiber_g", "protein_g": "protein_g",
    "cholesterol_mg": "cholesterol_mg", "sodium_mg": "sodium_mg", "calcium_mg": "calcium_mg",
    "iron_mg": "iron_mg", "magnesium_mg": "magnesium_mg", "potassium_mg": "potassium_mg",
    "folate_mcg": "folate_mcg", "thiamin_mg": "thiamin_mg",
    "niacin_equivalents_mg": "niacin_mg", "vitamin_a_iu_IU": "vitamin_a_iu",
    "vitamin_c_mg": "vitamin_c_mg",
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

TIME_UNITS = {"day": 1440, "days": 1440, "hr": 60, "hrs": 60, "min": 1, "mins": 1}


def parse_minutes(s: str) -> int | None:
    """'1 hr 10 mins' -> 70. None when empty or unparseable."""
    parts = re.findall(r"(\d+)\s*(days?|hrs?|mins?)", s or "")
    return sum(int(n) * TIME_UNITS[u] for n, u in parts) if parts else None


def num(s: str, cast=float):
    return cast(float(s)) if s not in ("", None) else None


FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅕": "1/5",
             "⅖": "2/5", "⅗": "3/5", "⅘": "4/5", "⅙": "1/6", "⅚": "5/6", "⅛": "1/8",
             "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
FRACTION_RE = re.compile(r"(?:(\d)[   ]?)?([" + "".join(FRACTIONS) + "])")


def normalize_fractions(s: str) -> str:
    """'1 ½ cups' -> '1 1/2 cups', '½ cup' -> '1/2 cup'."""
    s = FRACTION_RE.sub(lambda m: (m[1] + " " if m[1] else "") + FRACTIONS[m[2]], s)
    return re.sub(r"[  ]", " ", s)


SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(text.strip()) if s.strip()]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


def _embed_request(texts: list[str], attempts: int = 4) -> list[list[float]]:
    """Ollama occasionally returns a transient 400/500; retry, then halve the batch."""
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode()
    for attempt in range(attempts):
        req = urllib.request.Request(f"{OLLAMA_URL}/api/embed", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)["embeddings"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            detail = e.read()[:200] if isinstance(e, urllib.error.HTTPError) else e
            print(f"  embed retry {attempt + 1}/{attempts} ({len(texts)} texts): {detail}", flush=True)
            time.sleep(2 ** attempt)
    if len(texts) == 1:
        raise RuntimeError(f"cannot embed: {texts[0][:200]!r}")
    mid = len(texts) // 2
    return _embed_request(texts[:mid]) + _embed_request(texts[mid:])


def embed(texts: list[str]) -> np.ndarray:
    out = []
    for i in range(0, len(texts), EMBED_BATCH):
        out.extend(_embed_request(texts[i:i + EMBED_BATCH]))
    v = np.asarray(out, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def to_pgvector(v: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


# ---------------------------------------------------------------------------
# Chunking strategies. A cut turns each Recipe's directions (as sentences) into
# its Step chunk texts, for a whole batch of Recipes at once.
# ---------------------------------------------------------------------------


def semantic_chunks(sentences: list[str], vecs: np.ndarray, min_chars: int, max_chars: int,
                    break_percentile: int) -> list[str]:
    """Cut where neighbouring-sentence similarity drops below the recipe's
    break_percentile, merge pieces < min_chars into their more similar
    neighbour, split pieces > max_chars at their weakest internal link."""
    n = len(sentences)
    if n == 1:
        return sentences
    sims = np.sum(vecs[:-1] * vecs[1:], axis=1)  # sims[i] links sentence i and i+1
    threshold = np.percentile(sims, break_percentile)
    # pieces as [start, end) sentence ranges
    cuts = [i + 1 for i in range(n - 1) if sims[i] < threshold]
    bounds = [0, *cuts, n]
    pieces = [[bounds[k], bounds[k + 1]] for k in range(len(bounds) - 1)]

    def length(p):
        return len(" ".join(sentences[p[0]:p[1]]))

    # merge small pieces
    while len(pieces) > 1:
        small = [k for k, p in enumerate(pieces) if length(p) < min_chars]
        if not small:
            break
        k = small[0]
        left = sims[pieces[k][0] - 1] if k > 0 else -np.inf
        right = sims[pieces[k][1] - 1] if k < len(pieces) - 1 else -np.inf
        j = k - 1 if left >= right else k + 1
        a, b = sorted((k, j))
        pieces[a:b + 1] = [[pieces[a][0], pieces[b][1]]]

    # split large pieces
    def split(p):
        if length(p) <= max_chars or p[1] - p[0] < 2:
            return [p]
        cut = p[0] + 1 + int(np.argmin(sims[p[0]:p[1] - 1]))
        return split([p[0], cut]) + split([cut, p[1]])

    return [" ".join(sentences[s:e]) for p in pieces for s, e in split(p)]


def semantic_cut(batch: list[list[str]], min_chars: int, max_chars: int, break_percentile: int) -> list[list[str]]:
    """Needs every sentence embedded, so this is the slow one (~70 min for all Recipes)."""
    flat = [s for sents in batch for s in sents]
    vecs, out, offset = embed([f"search_document: {s}" for s in flat]), [], 0
    for sents in batch:
        v = vecs[offset:offset + len(sents)]
        out.append(semantic_chunks(sents, v, min_chars, max_chars, break_percentile) if sents else [])
        offset += len(sents)
    return out


def sentence_cut(batch: list[list[str]], sentences: int) -> list[list[str]]:
    """`sentences` consecutive sentences per chunk; the leftover forms its own chunk. No size cap."""
    return [[" ".join(sents[i:i + sentences]) for i in range(0, len(sents), sentences)] for sents in batch]


@cache
def wordpiece(name: str) -> Tokenizer:
    return Tokenizer.from_pretrained(name)


def fixed_cut(batch: list[list[str]], tokens: int, tokenizer: str) -> list[list[str]]:
    """Greedy windows of whole words, at most `tokens` WordPiece tokens each; sentence ends are
    ignored. A word is never split, so a single word longer than `tokens` gets a window of its own.
    WordPiece never merges across whitespace, so a window's count is the sum of its words' counts
    (true for BERT-style tokenizers only; a byte-level BPE one would need the window re-encoded)."""
    tok, out = wordpiece(tokenizer), []
    for sents in batch:
        words = " ".join(sents).split()
        sizes = [len(e.ids) for e in tok.encode_batch(words, add_special_tokens=False)] if words else []
        windows, start, used = [], 0, 0
        for i, n in enumerate(sizes):
            if used and used + n > tokens:
                windows.append(" ".join(words[start:i]))
                start, used = i, 0
            used += n
        if words:
            windows.append(" ".join(words[start:]))
        out.append(windows)
    return out


@dataclass(frozen=True)
class Strategy:
    method: str
    parameters: dict  # passed to cut as keyword arguments, and written to chunking_strategy.parameters
    cut: Callable[..., list[list[str]]]


# The only place a Chunking strategy is defined. A retune takes a new name.
STRATEGIES = {
    "semantic": Strategy("semantic", {"min_chars": 80, "max_chars": 400, "break_percentile": 25}, semantic_cut),
    "fixed": Strategy("fixed", {"tokens": 56, "tokenizer": "bert-base-uncased"}, fixed_cut),
    "sentence": Strategy("sentence", {"sentences": 3}, sentence_cut),
}


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------


def cmd_load(conn):
    with conn.transaction(), conn.cursor() as cur:
        # a reload renumbers Recipes, so kept chunks would point at the wrong ones.
        # The lock holds off a `chunk` from registering until the reload commits.
        cur.execute("LOCK TABLE chunking_strategy IN EXCLUSIVE MODE")
        names = [r[0] for r in cur.execute("SELECT name FROM chunking_strategy ORDER BY name")]
        if names:
            sys.exit(f"drop strategies first: {', '.join(names)}")

        if not CSV_PATH.exists():
            print(f"downloading {CSV_URL}")
            CSV_PATH.parent.mkdir(exist_ok=True)  # data/ is gitignored, so a fresh clone lacks it
            urllib.request.urlretrieve(CSV_URL, CSV_PATH)
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print(f"{len(rows)} rows")

        cur.execute("TRUNCATE category, author, recipe, recipe_nutrition, recipe_ingredient RESTART IDENTITY CASCADE")
        cats = sorted({r["category"] for r in rows})
        cur.executemany("INSERT INTO category (name) VALUES (%s)", [(c,) for c in cats])
        authors = sorted({r["author"].strip() for r in rows if r["author"].strip()})
        cur.executemany("INSERT INTO author (name) VALUES (%s)", [(a,) for a in authors])
        cat_id = dict(cur.execute("SELECT name, id FROM category").fetchall())
        author_id = dict(cur.execute("SELECT name, id FROM author").fetchall())

        seen, skipped = set(), 0
        for r in rows:
            if r["url"] in seen:
                skipped += 1
                continue
            seen.add(r["url"])
            rid = cur.execute(
                """INSERT INTO recipe (url, title, description, directions, image_url, category_id,
                     author_id, rating, rating_count, review_count, prep_minutes, cook_minutes,
                     total_minutes, servings, yields)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (r["url"], r["title"].strip(), r["description"].strip(), r["directions"].strip(),
                 r["image"] or None, cat_id[r["category"]], author_id.get(r["author"].strip()),
                 num(r["rating"]), num(r["rating_count"], int), num(r["review_count"], int),
                 parse_minutes(r["prep_time"]), parse_minutes(r["cook_time"]),
                 parse_minutes(r["total_time"]), num(r["servings"], int), r["yields"] or None),
            ).fetchone()[0]
            cur.execute(
                f"INSERT INTO recipe_nutrition (recipe_id, {', '.join(NUTRITION.values())}) "
                f"VALUES (%s{', %s' * len(NUTRITION)})",
                (rid, *(num(r[c]) for c in NUTRITION)),
            )
            lines = [l.strip() for l in r["ingredients"].split(";") if l.strip()]
            cur.executemany("INSERT INTO recipe_ingredient VALUES (%s, %s, %s)",
                            [(rid, i + 1, l) for i, l in enumerate(lines)])
    print(f"loaded {len(seen)} recipes ({skipped} duplicate urls skipped)")


# ---------------------------------------------------------------------------
# Building one strategy: register -> load_chunks -> staging_problems -> finish
# ---------------------------------------------------------------------------


# The recipe columns every chunk copies: category and the 11 other filter attributes (ADR-0001).
RECIPE_SQL = """SELECT r.id, r.title, r.description, r.directions, c.name, r.total_minutes,
                       r.prep_minutes, r.cook_minutes, r.rating, r.rating_count, r.servings,
                       n.calories, n.protein_g, n.fat_g, n.carbohydrates_g, n.sodium_mg,
                       (SELECT string_agg(line, '; ' ORDER BY position)
                          FROM recipe_ingredient i WHERE i.recipe_id = r.id)
                FROM recipe r JOIN category c ON c.id = r.category_id
                LEFT JOIN recipe_nutrition n ON n.recipe_id = r.id
                WHERE r.id = ANY(%s) ORDER BY r.id"""


def partition(name: str) -> str:
    return f"chunk_{name}"


def staging(name: str) -> str:
    return f"{partition(name)}_staging"


def register(conn, name: str):
    """The registry row (not loaded) and its staging table, together or not at all.
    Staging has chunk's columns and constraints but no identity (ATTACH refuses one):
    its id takes the parent's sequence instead. The keys are built here, not by the attach,
    so the attach doesn't build them under its lock; they're named for the final partition."""
    s = STRATEGIES[name]
    t = sql.Identifier(staging(name))
    with conn.transaction():
        conn.execute("INSERT INTO chunking_strategy (name, method, parameters) VALUES (%s, %s, %s)",
                     [name, s.method, Jsonb(s.parameters)])
        conn.execute(sql.SQL(
            """CREATE TABLE {t} (LIKE chunk INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
                 CHECK (strategy = {name}),
                 CONSTRAINT {pkey} PRIMARY KEY (id, strategy),
                 CONSTRAINT {ukey} UNIQUE (recipe_id, strategy, kind, position))""").format(
            t=t, name=sql.Literal(name), pkey=sql.Identifier(f"{partition(name)}_pkey"),
            ukey=sql.Identifier(f"{partition(name)}_key")))
        seq = conn.execute("SELECT pg_get_serial_sequence('chunk', 'id')").fetchone()[0]
        conn.execute(sql.SQL("ALTER TABLE {t} ALTER COLUMN id SET DEFAULT nextval({seq})").format(
            t=t, seq=sql.Literal(seq)))


def load_chunks(conn, name: str):
    """Chunk and embed every Recipe into staging, one transaction per batch.
    Reads only the recipe tables, never another strategy's chunks."""
    s = STRATEGIES[name]
    ids = [r[0] for r in conn.execute("SELECT id FROM recipe ORDER BY id").fetchall()]
    total, started = len(ids), time.time()
    insert = sql.SQL(
        """INSERT INTO {t} (recipe_id, strategy, kind, position, content, embedding,
             category, total_minutes, prep_minutes, cook_minutes, rating, rating_count,
             servings, calories, protein_g, fat_g, carbohydrates_g, sodium_mg)
           VALUES (%s,%s,%s,%s,%s,%s::vector,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""").format(
        t=sql.Identifier(staging(name)))
    print(f"{total} recipes to chunk as {name}", flush=True)

    for b in range(0, total, BATCH_SIZE):
        recipes = conn.execute(RECIPE_SQL, (ids[b:b + BATCH_SIZE],)).fetchall()
        steps = s.cut([split_sentences(normalize_fractions(r[3])) for r in recipes], **s.parameters)

        chunks = []
        for r, texts in zip(recipes, steps):
            rid, title, desc, filters = r[0], r[1], r[2], r[4:16]
            chunks.append((rid, "summary", 0, f"{title}\n{normalize_fractions(desc)}", filters))
            chunks.append((rid, "ingredients", 0,
                           f"{title}\nIngredients: {normalize_fractions(r[16] or '')}", filters))
            chunks += [(rid, "step", i + 1, f"{title}\n{t}", filters) for i, t in enumerate(texts)]

        vecs = embed([f"search_document: {c[3]}" for c in chunks])
        with conn.transaction(), conn.cursor() as cur:
            cur.executemany(insert, [(c[0], name, c[1], c[2], c[3], to_pgvector(v), *c[4])
                                     for c, v in zip(chunks, vecs)])

        done = b + len(recipes)
        rate = done / (time.time() - started)
        print(f"{done}/{total} recipes  {len(chunks)} chunks in batch  "
              f"eta {(total - done) / rate / 60:.0f} min", flush=True)


def staging_problems(conn, name: str) -> list[str]:
    """Names of the completeness checks staging fails; empty when it can be attached."""
    t = sql.Identifier(staging(name))
    per_recipe = conn.execute(sql.SQL(
        """SELECT count(*) FILTER (WHERE summaries <> 1),
                  count(*) FILTER (WHERE ingredients <> 1),
                  count(*) FILTER (WHERE steps = 0),
                  count(*) FILTER (WHERE steps > 0 AND (first <> 1 OR last <> steps OR distinct_steps <> steps))
           FROM (SELECT r.id,
                        count(c.id) FILTER (WHERE c.kind = 'summary') AS summaries,
                        count(c.id) FILTER (WHERE c.kind = 'ingredients') AS ingredients,
                        count(c.id) FILTER (WHERE c.kind = 'step') AS steps,
                        count(DISTINCT c.position) FILTER (WHERE c.kind = 'step') AS distinct_steps,
                        min(c.position) FILTER (WHERE c.kind = 'step') AS first,
                        max(c.position) FILTER (WHERE c.kind = 'step') AS last
                 FROM recipe r LEFT JOIN {t} c ON c.recipe_id = r.id
                 GROUP BY r.id) per_recipe""").format(t=t)).fetchone()
    null_embeddings = conn.execute(
        sql.SQL("SELECT count(*) FROM {t} WHERE embedding IS NULL").format(t=t)).fetchone()[0]
    # ADR-0001: every copied filter attribute still matches the recipe tables
    drifted = conn.execute(sql.SQL(
        """SELECT count(*)
           FROM {t} c
           JOIN recipe r ON r.id = c.recipe_id
           JOIN category cat ON cat.id = r.category_id
           LEFT JOIN recipe_nutrition nu ON nu.recipe_id = r.id
           WHERE (c.category, c.total_minutes, c.prep_minutes, c.cook_minutes, c.rating, c.rating_count,
                  c.servings, c.calories, c.protein_g, c.fat_g, c.carbohydrates_g, c.sodium_mg)
                 IS DISTINCT FROM
                 (cat.name, r.total_minutes, r.prep_minutes, r.cook_minutes, r.rating, r.rating_count,
                  r.servings, nu.calories, nu.protein_g, nu.fat_g, nu.carbohydrates_g, nu.sodium_mg)""").format(
        t=t)).fetchone()[0]
    checks = [
        ("every Recipe has exactly 1 Summary chunk", per_recipe[0]),
        ("every Recipe has exactly 1 Ingredients chunk", per_recipe[1]),
        ("every Recipe has at least 1 Step chunk", per_recipe[2]),
        ("Step positions run 1..n with no gaps", per_recipe[3]),
        ("no null embeddings", null_embeddings),
        ("ADR-0001 consistency check returns 0", drifted),
    ]
    return [check for check, failures in checks if failures]


def index_sql(table: str, index: str) -> sql.Composed:
    """sql/indexes.sql with its psql variables :"tbl" and :"idx" bound to these names."""
    names = {"tbl": table, "idx": index}
    parts = re.split(r':"(tbl|idx)"', (ROOT / "sql" / "indexes.sql").read_text())
    # re.split keeps the captured variable names at the odd positions
    return sql.Composed([sql.Identifier(names[p]) if i % 2 else sql.SQL(p) for i, p in enumerate(parts)])


def finish(conn, name: str):
    """Index staging, attach it as the strategy's partition and mark it loaded, in one go.
    The attach adopts the index (same definition as the parent's), so nothing is rebuilt."""
    with conn.transaction():
        conn.execute(index_sql(staging(name), f"{partition(name)}_search_idx"))  # also ANALYZEs it
        conn.execute(sql.SQL("ALTER TABLE chunk ATTACH PARTITION {t} FOR VALUES IN ({name})").format(
            t=sql.Identifier(staging(name)), name=sql.Literal(name)))
        conn.execute(sql.SQL("ALTER TABLE {t} RENAME TO {p}").format(
            t=sql.Identifier(staging(name)), p=sql.Identifier(partition(name))))
        conn.execute("ANALYZE chunk")  # the parent's stats; autovacuum never analyzes a partitioned table
        conn.execute("UPDATE chunking_strategy SET loaded_at = now() WHERE name = %s", [name])


def discard(conn, name: str):
    """Remove a strategy's partition or staging table, and its registry row."""
    with conn.transaction():
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {p}, {t}").format(
            p=sql.Identifier(partition(name)), t=sql.Identifier(staging(name))))
        conn.execute("DELETE FROM chunking_strategy WHERE name = %s", [name])


@contextmanager
def strategy_lock(conn, name: str):
    """Holds the strategy's advisory lock, so a second chunk or drop of it fails fast."""
    key = f"ingest:{name}"
    if not conn.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [key]).fetchone()[0]:
        sys.exit(f"{name} is already being built or dropped by another run")
    try:
        yield
    finally:
        conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", [key])


def is_loaded(conn, name: str) -> bool | None:
    """None when the strategy isn't registered."""
    row = conn.execute("SELECT loaded_at IS NOT NULL FROM chunking_strategy WHERE name = %s", [name]).fetchone()
    return None if row is None else row[0]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_chunk(conn, name: str):
    if name not in STRATEGIES:
        sys.exit(f"unknown strategy {name!r}; known: {', '.join(sorted(STRATEGIES))}")
    with strategy_lock(conn, name):
        state = is_loaded(conn, name)
        if state:
            sys.exit(f"{name} is loaded; run `drop {name}` first")
        if state is False:
            print(f"{name}: discarding an unfinished build", flush=True)
            discard(conn, name)
        register(conn, name)
        load_chunks(conn, name)
        problems = staging_problems(conn, name)
        if problems:
            sys.exit(f"{name} stays unloaded; check failed: {'; '.join(problems)}")
        finish(conn, name)
    print(f"{name} loaded")


def cmd_drop(conn, name: str, yes: bool):
    with strategy_lock(conn, name):
        state = is_loaded(conn, name)
        if state is None:
            sys.exit(f"{name} is not built; nothing to drop")
        if state and not yes:
            n = conn.execute("SELECT count(*) FROM chunk WHERE strategy = %s", [name]).fetchone()[0]
            sys.exit(f"{name} is loaded with {n} chunks; rerun with --yes to drop it")
        discard(conn, name)
    print(f"{name} dropped")


def run(conn, argv: list[str]):
    parser = argparse.ArgumentParser(prog="ingest.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    cmds = parser.add_subparsers(dest="cmd", required=True)
    cmds.add_parser("load")
    cmds.add_parser("chunk").add_argument("name")
    drop = cmds.add_parser("drop")
    drop.add_argument("name")
    drop.add_argument("--yes", action="store_true", help="drop even if loaded")
    a = parser.parse_args(argv)
    if a.cmd == "load":
        cmd_load(conn)
    elif a.cmd == "chunk":
        cmd_chunk(conn, a.name)
    else:
        cmd_drop(conn, a.name, a.yes)


if __name__ == "__main__":
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        run(conn, sys.argv[1:])
