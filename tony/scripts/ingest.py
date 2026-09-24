# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2", "numpy>=1.26"]
# ///
"""Load Shengtao/recipe into ParadeDB, then chunk + embed it.

    uv run scripts/ingest.py load      # CSV -> source tables (seconds)
    uv run scripts/ingest.py chunk     # semantic-v1 chunks + embeddings (resumable, ~70 min)
    uv run scripts/ingest.py index     # build the ParadeDB index
"""

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import psycopg

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "recipe.csv"
CSV_URL = "https://huggingface.co/datasets/Shengtao/recipe/resolve/main/recipe.csv"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5434/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
EMBED_BATCH = 256

CHUNKER = "semantic-v1"
MIN_CHARS = 80
MAX_CHARS = 400
BREAK_PERCENTILE = 25

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
# semantic-v1 chunker
# ---------------------------------------------------------------------------


def semantic_chunks(sentences: list[str], vecs: np.ndarray) -> list[str]:
    """Cut where neighbouring-sentence similarity drops below the recipe's
    BREAK_PERCENTILE, merge pieces < MIN_CHARS into their more similar
    neighbour, split pieces > MAX_CHARS at their weakest internal link."""
    n = len(sentences)
    if n == 1:
        return sentences
    sims = np.sum(vecs[:-1] * vecs[1:], axis=1)  # sims[i] links sentence i and i+1
    threshold = np.percentile(sims, BREAK_PERCENTILE)
    # pieces as [start, end) sentence ranges
    cuts = [i + 1 for i in range(n - 1) if sims[i] < threshold]
    bounds = [0, *cuts, n]
    pieces = [[bounds[k], bounds[k + 1]] for k in range(len(bounds) - 1)]

    def length(p):
        return len(" ".join(sentences[p[0]:p[1]]))

    # merge small pieces
    while len(pieces) > 1:
        small = [k for k, p in enumerate(pieces) if length(p) < MIN_CHARS]
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
        if length(p) <= MAX_CHARS or p[1] - p[0] < 2:
            return [p]
        cut = p[0] + 1 + int(np.argmin(sims[p[0]:p[1] - 1]))
        return split([p[0], cut]) + split([cut, p[1]])

    return [" ".join(sentences[s:e]) for p in pieces for s, e in split(p)]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_load(conn):
    if not CSV_PATH.exists():
        print(f"downloading {CSV_URL}")
        urllib.request.urlretrieve(CSV_URL, CSV_PATH)
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"{len(rows)} rows")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE category, author, recipe, recipe_nutrition, recipe_ingredient, chunk RESTART IDENTITY CASCADE")
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
    conn.commit()
    print(f"loaded {len(seen)} recipes ({skipped} duplicate urls skipped)")


def cmd_chunk(conn, batch_size=200):
    todo = conn.execute(
        """SELECT r.id FROM recipe r
           WHERE NOT EXISTS (SELECT 1 FROM chunk c WHERE c.recipe_id = r.id AND c.chunker = %s)
           ORDER BY r.id""", (CHUNKER,)).fetchall()
    todo = [t[0] for t in todo]
    total, started = len(todo), time.time()
    print(f"{total} recipes to chunk")

    for b in range(0, total, batch_size):
        ids = todo[b:b + batch_size]
        recipes = conn.execute(
            """SELECT r.id, r.title, r.description, r.directions, c.name, r.total_minutes,
                      r.prep_minutes, r.cook_minutes, r.rating, r.rating_count, r.servings,
                      n.calories, n.protein_g, n.fat_g, n.carbohydrates_g, n.sodium_mg,
                      (SELECT string_agg(line, '; ' ORDER BY position)
                         FROM recipe_ingredient i WHERE i.recipe_id = r.id)
               FROM recipe r JOIN category c ON c.id = r.category_id
               LEFT JOIN recipe_nutrition n ON n.recipe_id = r.id
               WHERE r.id = ANY(%s) ORDER BY r.id""", (ids,)).fetchall()

        # 1. sentence embeddings for every recipe in the batch, in one go
        sents = {r[0]: split_sentences(normalize_fractions(r[3])) for r in recipes}
        flat = [s for r in recipes for s in sents[r[0]]]
        svecs = embed([f"search_document: {s}" for s in flat])

        # 2. build chunks
        chunks, offset = [], 0
        for r in recipes:
            rid, title, desc = r[0], r[1], r[2]
            ss = sents[rid]
            steps = semantic_chunks(ss, svecs[offset:offset + len(ss)]) if ss else []
            offset += len(ss)
            filters = r[4:16]
            chunks.append((rid, "summary", 0, f"{title}\n{normalize_fractions(desc)}", filters))
            chunks.append((rid, "ingredients", 0,
                           f"{title}\nIngredients: {normalize_fractions(r[16] or '')}", filters))
            chunks += [(rid, "step", i + 1, f"{title}\n{t}", filters) for i, t in enumerate(steps)]

        # 3. chunk embeddings + insert (one transaction per batch, so resume is safe)
        cvecs = embed([f"search_document: {c[3]}" for c in chunks])
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO chunk (recipe_id, chunker, kind, position, content, embedding,
                     category, total_minutes, prep_minutes, cook_minutes, rating, rating_count,
                     servings, calories, protein_g, fat_g, carbohydrates_g, sodium_mg)
                   VALUES (%s,%s,%s,%s,%s,%s::vector,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [(c[0], CHUNKER, c[1], c[2], c[3], to_pgvector(v), *c[4])
                 for c, v in zip(chunks, cvecs)])
        conn.commit()

        done = min(b + batch_size, total)
        rate = done / (time.time() - started)
        print(f"{done}/{total} recipes  {len(chunks)} chunks in batch  "
              f"eta {(total - done) / rate / 60:.0f} min", flush=True)


def cmd_index(conn):
    conn.execute((ROOT / "sql" / "indexes.sql").read_text())
    conn.commit()
    print("chunk_search_idx built")


if __name__ == "__main__":
    cmds = {"load": cmd_load, "chunk": cmd_chunk, "index": cmd_index}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    with psycopg.connect(DATABASE_URL) as conn:
        cmds[sys.argv[1]](conn)
