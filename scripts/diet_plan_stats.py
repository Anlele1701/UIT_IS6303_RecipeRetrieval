"""What the Dietary Rule Engine does to the loaded cohort, and whether the search honours its Filters.

    uv run scripts/diet_plan_stats.py [--strategy semantic] [--queries "chicken dinner" "soup"]

1. Runs the engine on every patient in `ehr`: how many get 0/1/2/... Filters, how many have a limit
   the search cannot apply yet, how many have a condition we know but cannot turn into a limit.
2. For each distinct Filter set, runs a Sparse search (BM25, so no Ollama needed) per query under
   those Filters and counts the Chunks returned (cap 50), then checks every returned Recipe against
   recipe_nutrition independently of the index. Any violation is printed and exits 1.
"""

import argparse
import statistics
import sys
from collections import Counter
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # `uv run scripts/...` puts scripts/, not the repo root, on the path

from api import config, dietary_rules, patients, retrieval  # noqa: E402
from api.filters import SearchParams  # noqa: E402

DEFAULT_QUERIES = ["chicken dinner", "vegetable soup", "pasta salad", "dessert", "breakfast eggs"]


def plan_all(conn, rules) -> list[dietary_rules.DietPlan]:
    ids = [r[0] for r in conn.execute("SELECT id FROM ehr.patient ORDER BY id").fetchall()]
    filterable = dietary_rules.filterable_nutrients()
    return [dietary_rules.derive_diet_plan(patients.get_profile(conn, i), rules, filterable, config.MEALS_PER_DAY)
            for i in ids]


def violations(conn, recipe_ids: set[int], plan_filters: dict[str, float]) -> list[tuple[int, str, float]]:
    """Recipes whose recipe_nutrition breaks a Filter. A NULL nutrient counts as a violation (fail-safe)."""
    bad = []
    for key, limit in plan_filters.items():
        col = key.removeprefix("max_")
        rows = conn.execute(f"SELECT recipe_id, {col} FROM recipe_nutrition WHERE recipe_id = ANY(%s)",
                            [list(recipe_ids)]).fetchall()
        bad += [(rid, col, v) for rid, v in rows if v is None or v > limit]
    return bad


def report(conn, plans, strategy: str, queries: list[str]) -> int:
    n = len(plans)
    print(f"# Cohort: {n} patients, {config.MEALS_PER_DAY} meals/day\n")
    print("## Filters per patient")
    for k, c in sorted(Counter(len(p.filters) for p in plans).items()):
        print(f"- {k} Filters: {c} patients ({100 * c / n:.1f}%)")
    print("\n## Gaps")
    print(f"- limit the search cannot apply yet (unapplied_limits): "
          f"{sum(bool(p.unapplied_limits) for p in plans)} patients")
    print(f"- known condition with no usable limit (unsupported_conditions): "
          f"{sum(bool(p.unsupported_conditions) for p in plans)} patients")
    print(f"- no Filter at all (no_applicable_rules): {sum(p.status == 'no_applicable_rules' for p in plans)} patients")
    print("\n## Patients per Filter set")
    combos = Counter(tuple(sorted(p.filters.items())) for p in plans)
    for combo, c in combos.most_common():
        print(f"- {dict(combo) or '(none)'}: {c}")

    print(f"\n## Sparse search under each Filter set (strategy {strategy}, up to 50 Chunks per query)")
    print("| Filters | patients | " + " | ".join(queries) + " | violations |")
    print("|---|---|" + "---|" * len(queries) + "---|")
    total_bad = 0
    for combo, c in combos.most_common():
        if not combo:
            continue
        flt = dict(combo)
        counts, bad = [], []
        for q in queries:
            params = SearchParams(q=q, strategy=strategy, k=config.MAX_K, **flt)
            hits = retrieval.sparse(conn, params, config.MAX_K)
            counts.append(len(hits))
            bad += violations(conn, {h.recipe_id for h in hits}, flt) if hits else []
        total_bad += len(bad)
        print(f"| {flt} | {c} | " + " | ".join(map(str, counts)) + f" | {len(bad)} |")
        for rid, col, v in bad[:5]:
            print(f"|  VIOLATION recipe {rid}: {col} = {v} |")
    if combos:
        sizes = [len(p.evidence) for p in plans if p.evidence]
        print(f"\nmedian limits behind a patient's Filters: {statistics.median(sizes) if sizes else 0}")
    print(f"\nviolations: {total_bad}")
    return total_bad


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strategy", default="semantic")
    parser.add_argument("--queries", nargs="+", default=DEFAULT_QUERIES)
    args = parser.parse_args()
    rules = dietary_rules.load_rules(config.RULES_PATH)
    with psycopg.connect(config.DATABASE_URL) as conn:
        plans = plan_all(conn, rules)
        if not plans:
            sys.exit("no patients loaded; run scripts/load_synthea.py load first")
        sys.exit(1 if report(conn, plans, args.strategy, args.queries) else 0)


if __name__ == "__main__":
    main()
