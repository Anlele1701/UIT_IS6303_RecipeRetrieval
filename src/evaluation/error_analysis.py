"""
Pick out the queries worth reading by hand, from saved per-query runs.

    python -m src.evaluation.error_analysis

docs/11_ERROR_ANALYSIS.md asks for concrete cases rather than metrics alone.
Searching 300 queries by hand for the interesting ones is the slow part, so
this selects them by the disagreement patterns that actually explain
something -- one method finding what another missed, fusion losing a hit both
inputs had, the reranker demoting a correct hit -- and renders them as cards.

Nothing here decides whether a case is a true retrieval error or a gap in the
constructed ground truth; that judgement stays manual, which is why each card
prints the top hits next to the labelled recipe.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from src.config import CONFIG
from src.db import connect
from src.evaluation.run_experiments import load_run, run_path

DEFAULT_CONFIGS = ("bm25", "dense", "hybrid_rrf", "hybrid_rerank")
TOP_SHOWN = 5


def _recipe_details(recipe_ids: list[int]) -> dict[int, tuple[str, str]]:
    if not recipe_ids:
        return {}
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT recipe_idx, name, image_path
            FROM raw.recipes
            WHERE recipe_idx = ANY(%s)
            """,
            (list(recipe_ids),),
        ).fetchall()
    return {int(r[0]): (r[1], r[2] or "") for r in rows}


def _rank_text(rank: int | None) -> str:
    return f"#{rank}" if rank else "miss"


def _hit(rank: int | None, k: int = 10) -> bool:
    return rank is not None and rank <= k


def select_cases(records_by_config: dict[str, dict], configs: list[str]) -> dict[str, list[int]]:
    """Group query ids by the disagreement pattern they illustrate."""
    query_ids = sorted(next(iter(records_by_config.values())).keys())
    cases: dict[str, list[int]] = {
        "dense_wins_bm25_misses": [],
        "bm25_wins_dense_misses": [],
        "fusion_loses_both_inputs": [],
        "rerank_demotes_correct_hit": [],
        "every_configuration_misses": [],
    }

    for query_id in query_ids:
        ranks = {
            config: records_by_config[config][query_id].gold_rank
            for config in configs
            if query_id in records_by_config[config]
        }
        if "bm25" in ranks and "dense" in ranks:
            if _hit(ranks["dense"]) and not _hit(ranks["bm25"]):
                cases["dense_wins_bm25_misses"].append(query_id)
            if _hit(ranks["bm25"]) and not _hit(ranks["dense"]):
                cases["bm25_wins_dense_misses"].append(query_id)
            # Fusion is supposed to be a safety net; when it drops a hit that
            # both inputs had, the RRF weighting is the thing to explain.
            if (
                "hybrid_rrf" in ranks
                and _hit(ranks["bm25"])
                and _hit(ranks["dense"])
                and not _hit(ranks["hybrid_rrf"])
            ):
                cases["fusion_loses_both_inputs"].append(query_id)
        if "hybrid_rrf" in ranks and "hybrid_rerank" in ranks:
            before, after = ranks["hybrid_rrf"], ranks["hybrid_rerank"]
            if _hit(before) and (after is None or after > before):
                cases["rerank_demotes_correct_hit"].append(query_id)
        if ranks and not any(_hit(rank) for rank in ranks.values()):
            cases["every_configuration_misses"].append(query_id)

    return cases


CASE_TITLES = {
    "dense_wins_bm25_misses": "Dense retrieves it, BM25 does not",
    "bm25_wins_dense_misses": "BM25 retrieves it, dense does not",
    "fusion_loses_both_inputs": "RRF drops a hit that both inputs had",
    "rerank_demotes_correct_hit": "The cross-encoder demotes a correct hit",
    "every_configuration_misses": "No configuration retrieves the labelled recipe",
}


def _render_card(
    record,
    ranks: dict[str, int | None],
    focus_record,
    details: dict[int, tuple[str, str]],
) -> list[str]:
    gold_name, gold_image = details.get(record.source_recipe_idx, ("(unknown)", ""))
    lines = [
        f"**Query** (`{record.family}`): {record.query_text}",
        "",
    ]
    if record.substitutions:
        lines += [
            f"Rewritten from: {record.base_query_text} "
            f"({'; '.join(record.substitutions)})",
            "",
        ]
    lines += [
        f"**Labelled recipe**: #{record.source_recipe_idx} {gold_name}"
        + (f" (`{gold_image}`)" if gold_image else ""),
        "",
        "Rank of the labelled recipe: "
        + ", ".join(f"{config} {_rank_text(rank)}" for config, rank in ranks.items()),
        "",
        f"Top {TOP_SHOWN} returned by `{focus_record[0]}`:",
        "",
    ]
    for position, (recipe_idx, name) in enumerate(
        zip(focus_record[1].ranked_ids[:TOP_SHOWN], focus_record[1].top_names[:TOP_SHOWN]),
        start=1,
    ):
        marker = " <- labelled" if recipe_idx == record.source_recipe_idx else ""
        lines.append(f"{position}. #{recipe_idx} {name}{marker}")
    lines.append("")
    return lines


def build_report(configs: list[str], per_case: int) -> str:
    records_by_config = {}
    for config in configs:
        _, records = load_run(config)
        records_by_config[config] = {r.query_id: r for r in records}

    cases = select_cases(records_by_config, configs)
    reference = records_by_config[configs[0]]

    sections = [
        "# Error analysis",
        "",
        "Generated by `python -m src.evaluation.error_analysis`. Cases are "
        "selected automatically from the per-query records of "
        + ", ".join(f"`{c}`" for c in configs)
        + "; the interpretation of each one is written by hand in "
        "`docs/11_ERROR_ANALYSIS.md`.",
        "",
        "## How often each pattern occurs",
        "",
        "| pattern | queries |",
        "|---|---|",
    ]
    for key, ids in cases.items():
        sections.append(f"| {CASE_TITLES[key]} | {len(ids)} |")
    sections.append("")

    # Miss rate per family shows which query type each method struggles with.
    sections += ["## Recall@10 misses by query family", "", "| config | " + " | ".join(
        sorted({r.family for r in reference.values()})
    ) + " |"]
    families = sorted({r.family for r in reference.values()})
    sections.append("|" + "|".join("---" for _ in range(len(families) + 1)) + "|")
    for config in configs:
        counts = Counter(
            record.family
            for record in records_by_config[config].values()
            if not _hit(record.gold_rank)
        )
        totals = Counter(record.family for record in records_by_config[config].values())
        sections.append(
            f"| `{config}` | "
            + " | ".join(f"{counts.get(f, 0)}/{totals.get(f, 0)}" for f in families)
            + " |"
        )
    sections.append("")

    needed = {
        query_id
        for ids in cases.values()
        for query_id in ids[:per_case]
    }
    details = _recipe_details(
        [reference[query_id].source_recipe_idx for query_id in needed if query_id in reference]
    )

    for key, ids in cases.items():
        sections += [f"## {CASE_TITLES[key]}", ""]
        if not ids:
            sections += ["None.", ""]
            continue
        # The focus list is the method whose behaviour the pattern is about.
        focus_config = {
            "dense_wins_bm25_misses": "bm25",
            "bm25_wins_dense_misses": "dense",
            "fusion_loses_both_inputs": "hybrid_rrf",
            "rerank_demotes_correct_hit": "hybrid_rerank",
            "every_configuration_misses": configs[0],
        }[key]
        if focus_config not in records_by_config:
            focus_config = configs[0]

        for query_id in ids[:per_case]:
            record = reference[query_id]
            ranks = {
                config: records_by_config[config][query_id].gold_rank
                for config in configs
                if query_id in records_by_config[config]
            }
            sections += _render_card(
                record,
                ranks,
                (focus_config, records_by_config[focus_config][query_id]),
                details,
            )
            sections.append("---")
            sections.append("")

    return "\n".join(sections) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--configs",
        default=",".join(DEFAULT_CONFIGS),
        help="Comma-separated configuration names to compare",
    )
    parser.add_argument("--per-case", type=int, default=3, help="Cards per pattern")
    parser.add_argument("--out", default=f"{CONFIG.experiments_dir}/error_cases.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configs = [c for c in args.configs.split(",") if c]

    missing = [c for c in configs if not run_path(c).is_file()]
    if missing:
        print(f"missing runs: {', '.join(missing)}; run them first", file=sys.stderr)
        return 1

    report = build_report(configs, args.per_case)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
