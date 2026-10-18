"""M2 step 1: the 200-recipe allergen audit sample, stratified by category, with a 50-recipe holdout.

    uv run scripts/make_allergen_sample.py            # refuses to overwrite an existing sample
    uv run scripts/make_allergen_sample.py --force    # only with Thy's go-ahead (CLAUDE.md rule 3)

Reads recipe and category only: never tags or checker output, so the sample cannot lean towards
what either system gets right or wrong. Writes eval/labels/allergen_sample.csv (labeling order,
recipe_id, category, split) and allergen_sample.json (allocation, seeds, sha256).
"""

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402

from api import config  # noqa: E402

OUT = ROOT / "eval" / "labels" / "allergen_sample.csv"
SIZE, HOLDOUT = 200, 50
SEED, HOLDOUT_SEED, ORDER_SEED = 42, 43, 44


def allocate(sizes: dict[str, int], total: int) -> dict[str, int]:
    """Proportional allocation, rounded by largest remainder; ties broken by name for determinism."""
    n = sum(sizes.values())
    exact = {c: total * s / n for c, s in sizes.items()}
    alloc = {c: int(e) for c, e in exact.items()}
    for c in sorted(exact, key=lambda c: (-(exact[c] - alloc[c]), c))[:total - sum(alloc.values())]:
        alloc[c] += 1
    return alloc


def draw(by_category: dict[str, list[int]]) -> list[dict]:
    """The sample rows, deterministic for the given recipe lists."""
    alloc = allocate({c: len(ids) for c, ids in by_category.items()}, SIZE)
    rnd = random.Random(SEED)
    picked = {c: rnd.sample(sorted(ids), alloc[c]) for c, ids in sorted(by_category.items())}
    held_alloc = allocate({c: len(p) for c, p in picked.items() if p}, HOLDOUT)
    rnd_h = random.Random(HOLDOUT_SEED)
    holdout = {rid for c, p in sorted(picked.items()) if p for rid in rnd_h.sample(p, held_alloc[c])}
    rows = [{"recipe_id": rid, "category": c, "split": "holdout" if rid in holdout else "dev"}
            for c, p in sorted(picked.items()) for rid in p]
    random.Random(ORDER_SEED).shuffle(rows)  # labeling order mixes categories and splits
    for i, r in enumerate(rows, 1):
        r["sample_order"] = i
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true", help="overwrite an existing sample (ask Thy first)")
    a = p.parse_args()
    if OUT.exists() and not a.force:
        sys.exit(f"{OUT.name} exists; it may already be labeled. Rerun with --force only if Thy agrees.")
    with psycopg.connect(config.DATABASE_URL) as conn:
        by_category: dict[str, list[int]] = {}
        for rid, cat in conn.execute("SELECT r.id, c.name FROM recipe r JOIN category c ON c.id = r.category_id"):
            by_category.setdefault(cat, []).append(rid)
    rows = draw(by_category)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sample_order", "recipe_id", "category", "split"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    alloc = allocate({c: len(ids) for c, ids in by_category.items()}, SIZE)
    meta = {"size": SIZE, "holdout": HOLDOUT, "seeds": {"sample": SEED, "holdout": HOLDOUT_SEED, "order": ORDER_SEED},
            "recipes": sum(len(v) for v in by_category.values()),
            "per_category": {c: {"recipes": len(by_category[c]), "sampled": alloc[c],
                                 "holdout": sum(1 for r in rows if r["category"] == c and r["split"] == "holdout")}
                             for c in sorted(by_category)},
            "categories_with_no_sample": sorted(c for c, k in alloc.items() if k == 0),
            "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()}
    OUT.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
