"""D5 lexicon bootstrap: data/lexicon/ingredients.csv and allergen_map.csv from the corpus and the rules.

    uv run python -m lexicon.build_lexicon bootstrap        # from scripts/: rules + frequency, no model
    uv run python -m lexicon.build_lexicon suggest          # qwen2.5:7b proposes a base name for unmatched names
    uv run python -m lexicon.build_lexicon apply-suggestions  # accepted suggestions -> manual_synonyms.csv

Canonical ingredients are the hand-written groups in manual_synonyms.csv plus the TOP_N most frequent
"cores" (parsed name without descriptor/size words, singular), skipping cores that already map to one.
Each canonical also gets its most frequent full names as synonyms, so the longest match reaches it.
Food group and allergens come from rules.csv (lexicon.tagger). Inputs are the DB's raw lines.
"""

import argparse
import collections
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx
import psycopg

from .normalize import LEXICON, Lexicon, core, key
from .parse import parse_line
from .tagger import ALLERGENS, Rules

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://recipe:recipe@localhost:5435/recipe")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
QU_MODEL = os.environ.get("QU_MODEL", "qwen2.5:7b")
TOP_N = 1500
NAMES_PER_CANONICAL = 6
SUGGEST_MIN_LINES = 2  # unmatched names on fewer lines are left unknown
BATCH = 40
SEED = 42
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "lexicon_suggest.jsonl"
JUNK = {"", "and", "or", "teaspoon", "fat free", "breast", "s"}


def raw_lines(conn) -> list[tuple[str, int]]:
    return conn.execute("SELECT line, count(*) FROM recipe_ingredient GROUP BY line").fetchall()


def is_compound(c: str) -> bool:
    ws = c.split()
    return not ws or "and" in ws or "or" in ws or ws[0].isdigit()


def read_manual() -> dict[str, list[str]]:
    with open(LEXICON / "manual_synonyms.csv", newline="", encoding="utf-8") as f:
        return {r["canonical"]: [s for s in r["synonyms"].split("|") if s] for r in csv.DictReader(f)}


def bootstrap(conn) -> dict:
    cores: collections.Counter = collections.Counter()
    names: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for line, n in raw_lines(conn):
        p = parse_line(line)
        if p.name:
            c = core(p.name)
            cores[c] += n
            names[c][key(p.name)] += n

    manual = read_manual()
    entries: dict[str, dict] = {}  # canonical -> {synonyms, origin, lines}
    taken: dict[str, str] = {}  # key -> canonical
    for canonical, syns in manual.items():
        entries[canonical] = {"synonyms": list(syns), "origin": "manual", "lines": 0}
        for s in [canonical, *syns]:
            taken[key(s)] = canonical
    for c, n in cores.most_common():
        if sum(1 for e in entries.values() if e["origin"] == "rule") >= TOP_N:
            break
        if c in JUNK or is_compound(c):
            continue
        canonical = taken.get(key(c))
        if canonical is None:
            canonical = c
            entries[c] = {"synonyms": [], "origin": "rule", "lines": 0}
            taken[key(c)] = c
        entries[canonical]["lines"] += n
        for name, _ in names[c].most_common(NAMES_PER_CANONICAL):
            if name not in taken:
                taken[name] = canonical
                entries[canonical]["synonyms"].append(name)

    rules = Rules.from_csv()
    with open(LEXICON / "ingredients.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["canonical", "synonyms", "group", "origin", "lines"])
        for canonical, e in sorted(entries.items(), key=lambda kv: -kv[1]["lines"]):
            w.writerow([canonical, "|".join(e["synonyms"]), rules.tags(canonical).group, e["origin"], e["lines"]])

    rows = []
    for canonical, e in entries.items():
        t = rules.tags(canonical)
        if t.allergens:
            hidden = any(k == "hidden" for k in t.allergens.values())
            rows.append((not hidden, -e["lines"], canonical,
                         "|".join(a for a in ALLERGENS if a in t.allergens),
                         "hidden" if hidden else "direct", "|".join(t.rules), e["lines"]))
    with open(LEXICON / "allergen_map.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["canonical", "allergens", "kind", "rules", "lines"])
        for *_, canonical, allergens, kind, fired, lines in sorted(rows):
            w.writerow([canonical, allergens, kind, fired, lines])

    lex = Lexicon.from_csv()
    total = sum(n for _, n in raw_lines(conn))
    matched = unmatched = 0
    for line, n in raw_lines(conn):
        p = parse_line(line)
        if p.name and lex.match(p.name):
            matched += n
        else:
            unmatched += n
    stats = {"canonicals": len(entries), "manual": len(manual), "top_n": TOP_N,
             "lines": total, "lines_matched": matched, "coverage": round(matched / total, 4)}
    print(json.dumps(stats, indent=2))
    return stats


# ---------------------------------------------------------------------------
# LLM suggestions for unmatched names (reviewed by Thy before use)
# ---------------------------------------------------------------------------

SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"name": {"type": "string"}, "base": {"type": "string"}},
    "required": ["name", "base"]}}}, "required": ["items"]}
PROMPT = """For each recipe ingredient name below, give the plain generic English ingredient it is,
in 1-3 lowercase words, as a cook would write it in a shopping list (drop brands, sizes and preparation).
If it is not food (foil, skewers), answer "nonfood". Reply in JSON.
Names:
{names}"""


def cached_llm(names: list[str], client: httpx.Client) -> dict[str, str]:
    h = hashlib.sha256(json.dumps([QU_MODEL, PROMPT, names]).encode()).hexdigest()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["hash"] == h:
                return row["out"]
    r = client.post(f"{OLLAMA_URL}/api/chat", json={
        "model": QU_MODEL, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0, "seed": SEED, "num_ctx": 4096},
        "messages": [{"role": "user", "content": PROMPT.format(names="\n".join(f"- {n}" for n in names))}]})
    r.raise_for_status()
    items = json.loads(r.json()["message"]["content"]).get("items", [])
    out = {i["name"].strip().lower(): i["base"].strip().lower() for i in items}
    with open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"hash": h, "names": names, "out": out}) + "\n")
    return out


def suggest(conn):
    lex = Lexicon.from_csv()
    unmatched: collections.Counter = collections.Counter()
    for line, n in raw_lines(conn):
        p = parse_line(line)
        if p.name and not lex.match(p.name):
            unmatched[p.name] += n
    todo = [(name, n) for name, n in unmatched.most_common() if n >= SUGGEST_MIN_LINES]
    print(f"{len(unmatched)} unmatched names, {len(todo)} on >= {SUGGEST_MIN_LINES} lines", flush=True)
    rows = []
    with httpx.Client(timeout=900) as client:
        for b in range(0, len(todo), BATCH):
            batch = todo[b:b + BATCH]
            out = cached_llm([name for name, _ in batch], client)
            for name, n in batch:
                base = out.get(name, "")
                proposed = "nonfood" if base == "nonfood" else (lex.match(base) or [f"NEW:{base}" if base else ""])[0]
                rows.append([name, n, base, proposed, "", ""])
            print(f"{b + len(batch)}/{len(todo)}", flush=True)
    with open(LEXICON / "synonym_suggestions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["variant", "lines", "llm_base", "proposed_canonical", "accept", "corrected_canonical"])
        w.writerows(rows)
    print(f"wrote {len(rows)} suggestions; fill accept=y (and corrected_canonical to override)")


def apply_suggestions():
    manual = read_manual()
    added = 0
    with open(LEXICON / "synonym_suggestions.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["accept"].strip().lower() not in {"y", "yes", "1", "x"}:
                continue
            target = (r["corrected_canonical"] or r["proposed_canonical"]).strip()
            target = target.removeprefix("NEW:")
            if not target or target == "nonfood":
                continue
            manual.setdefault(target, [])
            if r["variant"] not in manual[target]:
                manual[target].append(r["variant"])
                added += 1
    with open(LEXICON / "manual_synonyms.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["canonical", "synonyms"])
        for canonical, syns in manual.items():
            w.writerow([canonical, "|".join(syns)])
    print(f"added {added} accepted synonyms to manual_synonyms.csv; run bootstrap again")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["bootstrap", "suggest", "apply-suggestions"])
    a = p.parse_args()
    if a.command == "apply-suggestions":
        return apply_suggestions()
    with psycopg.connect(DATABASE_URL) as conn:
        (bootstrap if a.command == "bootstrap" else suggest)(conn)


if __name__ == "__main__":
    sys.exit(main())
