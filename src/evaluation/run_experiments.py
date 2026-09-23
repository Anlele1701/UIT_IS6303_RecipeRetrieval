"""
Run every retrieval configuration in docs/09_EXPERIMENTS.md and
docs/10_ABLATION_STUDY.md against one shared query set.

    python -m src.evaluation.run_experiments run --groups A,B
    python -m src.evaluation.run_experiments report

`run` executes configurations and writes one JSON summary plus one
per-query JSONL per configuration; `report` rebuilds experiments/results.csv
and experiments/report.md from those files without re-running retrieval, so
tables can be regenerated freely while the expensive runs stay cached.
"""

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config import CONFIG
from src.db import connect
from src.evaluation.evaluator import (
    DEFAULT_DEPTH,
    DEFAULT_K_VALUES,
    EncodeClock,
    TimedQueryEncoder,
    evaluate,
    records_from_dicts,
    records_to_dicts,
    per_query_scores,
)
from src.evaluation.metrics import paired_bootstrap
from src.evaluation.queries import load_query_set

DEFAULT_QUERY_SET = f"{CONFIG.experiments_dir}/queries_v1.json"
RUNS_DIR = f"{CONFIG.experiments_dir}/runs"

# Pool that RRF fuses over. Fixed across every rerank configuration so the
# 20/50/100 rerank pools are nested subsets of one candidate list rather than
# three differently-built lists.
FUSION_POOL = 100

CSV_COLUMNS = [
    "config", "group", "method", "chunk_profile", "embedding_profile",
    "candidate_pool", "rrf_k", "rerank_pool", "num_queries",
    "recall@1", "recall@5", "recall@10", "recall@10_ci_low", "recall@10_ci_high",
    "mrr", "ndcg@10",
    "latency_p50_ms", "latency_p95_ms", "encode_mean_ms", "search_mean_ms",
]


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    group: str
    method: str  # bm25 | dense | hybrid_sql | hybrid_python | hybrid_rerank
    chunk_profile: str = CONFIG.chunk_profile_name
    embedding_profile: str = CONFIG.embedding_profile_name
    candidate_pool: int = FUSION_POOL
    rrf_k: int = 60
    rerank_pool: int = 0

    @property
    def needs_embeddings(self) -> bool:
        return self.method != "bm25"


GROUP_LABELS = {
    "A": "A - main retrieval comparison",
    "B": "B - where the fusion logic lives",
    "C": "C - reranker candidate pool",
    "D": "D - text representation (which fields are indexed)",
    "E": "E - chunk strategy",
    "F": "F - embedding model",
    "G": "G - RRF constant k",
}


def build_registry() -> dict[str, ExperimentConfig]:
    configs: list[ExperimentConfig] = [
        # A - the four configurations the course requires as a minimum.
        ExperimentConfig("bm25", "A", "bm25"),
        ExperimentConfig("dense", "A", "dense"),
        ExperimentConfig("hybrid_rrf", "A", "hybrid_sql"),
        ExperimentConfig("hybrid_rerank", "A", "hybrid_rerank", rerank_pool=50),
        # B - identical fusion, different tier.
        ExperimentConfig("hybrid_rrf_python", "B", "hybrid_python"),
        # C - how many candidates the cross-encoder gets to see.
        ExperimentConfig("rerank_pool20", "C", "hybrid_rerank", rerank_pool=20),
        ExperimentConfig("rerank_pool50", "C", "hybrid_rerank", rerank_pool=50),
        ExperimentConfig("rerank_pool100", "C", "hybrid_rerank", rerank_pool=100),
        # G - fusion constant.
        ExperimentConfig("hybrid_rrfk20", "G", "hybrid_sql", rrf_k=20),
        ExperimentConfig("hybrid_rrfk120", "G", "hybrid_sql", rrf_k=120),
    ]

    # D - text representation: same pipeline, fewer fields in the chunk.
    for profile, suffix in (("name_only_v1", "name"), ("name_ingredients_v1", "name_ing")):
        configs += [
            ExperimentConfig(f"bm25_{suffix}", "D", "bm25", chunk_profile=profile),
            ExperimentConfig(f"dense_{suffix}", "D", "dense", chunk_profile=profile),
            ExperimentConfig(f"hybrid_{suffix}", "D", "hybrid_sql", chunk_profile=profile),
        ]

    # E - one chunk per recipe vs one chunk per field.
    configs += [
        ExperimentConfig("bm25_fieldchunk", "E", "bm25", chunk_profile="field_chunk_v1"),
        ExperimentConfig("dense_fieldchunk", "E", "dense", chunk_profile="field_chunk_v1"),
        ExperimentConfig("hybrid_fieldchunk", "E", "hybrid_sql", chunk_profile="field_chunk_v1"),
    ]

    # F - embedding model, everything else held fixed.
    for profile, suffix in (("bge_small_en_v15_v1", "bge"), ("e5_small_v2_v1", "e5")):
        configs += [
            ExperimentConfig(f"dense_{suffix}", "F", "dense", embedding_profile=profile),
            ExperimentConfig(f"hybrid_{suffix}", "F", "hybrid_sql", embedding_profile=profile),
        ]

    return {config.name: config for config in configs}


def available_profiles() -> tuple[set[str], set[str]]:
    with connect() as connection:
        chunks = {
            row[0]
            for row in connection.execute(
                "SELECT profile_name FROM retrieval.chunk_profiles"
            ).fetchall()
        }
        embeddings = {
            row[0]
            for row in connection.execute(
                """
                SELECT p.profile_name
                FROM retrieval.embedding_profiles AS p
                WHERE EXISTS (
                    SELECT 1 FROM retrieval.chunk_embeddings AS e
                    WHERE e.embedding_profile_id = p.embedding_profile_id
                )
                """
            ).fetchall()
        }
    return chunks, embeddings


class RetrieverFactory:
    """
    Builds retrievers for a configuration while sharing the expensive pieces.

    One SentenceTransformer per embedding profile and one CrossEncoder for the
    whole session: without this, a full sweep reloads the same models dozens
    of times and the load cost leaks into the first queries of each run.
    """

    def __init__(self, clock: EncodeClock):
        self.clock = clock
        self._encoders: dict[str, object] = {}
        self._reranker = None

    def encoder(self, embedding_profile: str):
        if embedding_profile not in self._encoders:
            from src.retrieval.postgres import PostgresQueryEncoder

            self._encoders[embedding_profile] = TimedQueryEncoder(
                PostgresQueryEncoder(embedding_profile), self.clock
            )
        return self._encoders[embedding_profile]

    def reranker(self):
        if self._reranker is None:
            from src.retrieval.reranker import Reranker

            self._reranker = Reranker(model_name=CONFIG.reranker_model_name)
        return self._reranker

    def build(self, config: ExperimentConfig):
        from src.retrieval.postgres import (
            PostgresDenseRetriever,
            PostgresHybridRetriever,
            PostgresSparseRetriever,
            PythonRRFHybridRetriever,
        )
        from src.retrieval.reranker import HybridRerankRetriever

        if config.method == "bm25":
            return PostgresSparseRetriever(config.chunk_profile, load_images=False)

        encoder = self.encoder(config.embedding_profile)

        if config.method == "dense":
            return PostgresDenseRetriever(
                config.chunk_profile,
                config.embedding_profile,
                encoder=encoder,
                load_images=False,
            )

        if config.method == "hybrid_python":
            return PythonRRFHybridRetriever(
                config.chunk_profile,
                config.embedding_profile,
                candidate_pool=config.candidate_pool,
                rrf_k=config.rrf_k,
                encoder=encoder,
                load_images=False,
            )

        hybrid = PostgresHybridRetriever(
            config.chunk_profile,
            config.embedding_profile,
            candidate_pool=FUSION_POOL,
            rrf_k=config.rrf_k,
            encoder=encoder,
            load_images=False,
        )
        if config.method == "hybrid_sql":
            return hybrid
        if config.method == "hybrid_rerank":
            return HybridRerankRetriever(
                hybrid, self.reranker(), candidate_pool=config.rerank_pool
            )
        raise ValueError(f"Unknown method: {config.method}")


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def provenance(config: ExperimentConfig, query_metadata: dict) -> dict:
    """Everything needed to reproduce a row of the results table."""
    return {
        "config": asdict(config),
        "git_commit": git_commit(),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_name": CONFIG.dataset_name,
        "dataset_revision": CONFIG.dataset_revision,
        "corpus_split": CONFIG.corpus_split,
        "subset_size": CONFIG.subset_size,
        "subset_seed": CONFIG.seed,
        "embedding_model": None
        if config.method == "bm25"
        else _embedding_model_name(config.embedding_profile),
        "reranker_model": CONFIG.reranker_model_name if config.rerank_pool else None,
        "fusion_pool": FUSION_POOL if "hybrid" in config.method else None,
        "query_set": query_metadata,
    }


def _embedding_model_name(embedding_profile: str) -> str | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT model_name FROM retrieval.embedding_profiles WHERE profile_name = %s",
            (embedding_profile,),
        ).fetchone()
    return row[0] if row else None


def run_path(name: str) -> Path:
    return Path(RUNS_DIR) / f"{name}.json"


def records_path(name: str) -> Path:
    return Path(RUNS_DIR) / f"{name}.per_query.jsonl"


def save_run(name: str, payload: dict, records) -> None:
    Path(RUNS_DIR).mkdir(parents=True, exist_ok=True)
    with open(run_path(name), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(records_path(name), "w", encoding="utf-8") as f:
        for row in records_to_dicts(records):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_run(name: str) -> tuple[dict, list]:
    with open(run_path(name), "r", encoding="utf-8") as f:
        payload = json.load(f)
    with open(records_path(name), "r", encoding="utf-8") as f:
        records = records_from_dicts([json.loads(line) for line in f if line.strip()])
    return payload, records


def completed_runs() -> list[str]:
    registry = build_registry()
    return [name for name in registry if run_path(name).is_file()]


def command_run(args) -> int:
    registry = build_registry()
    queries, query_metadata = load_query_set(args.queries)
    if args.limit:
        queries = queries[: args.limit]

    if args.configs:
        selected = [registry[name] for name in args.configs.split(",")]
    else:
        groups = set(args.groups.split(",")) if args.groups else set(GROUP_LABELS)
        selected = [c for c in registry.values() if c.group in groups]

    chunk_profiles, embedding_profiles = available_profiles()
    clock = EncodeClock()
    factory = RetrieverFactory(clock)

    for config in selected:
        if config.chunk_profile not in chunk_profiles:
            print(f"skip {config.name}: chunk profile {config.chunk_profile!r} not indexed")
            continue
        if config.needs_embeddings and config.embedding_profile not in embedding_profiles:
            print(f"skip {config.name}: embedding profile {config.embedding_profile!r} not indexed")
            continue
        if run_path(config.name).is_file() and not args.force:
            print(f"skip {config.name}: already run (use --force to redo)")
            continue

        print(f"running {config.name} ({config.method}, {config.chunk_profile}) ...", flush=True)
        retriever = factory.build(config)
        summary, records = evaluate(
            retriever.search,
            queries,
            k_values=DEFAULT_K_VALUES,
            depth=args.depth,
            clock=clock if config.needs_embeddings else None,
        )
        save_run(config.name, {**provenance(config, query_metadata), "results": summary}, records)
        print(
            f"  recall@10={summary['recall@10']:.3f} "
            f"mrr={summary['mrr']:.3f} ndcg@10={summary['ndcg@10']:.3f} "
            f"p50={summary['latency_p50_ms']:.1f}ms"
        )

    return command_report(args)


def _csv_row(name: str, payload: dict, summary: dict) -> dict:
    config = payload["config"]
    row = {
        "config": name,
        "group": config["group"],
        "method": config["method"],
        "chunk_profile": config["chunk_profile"],
        "embedding_profile": "" if config["method"] == "bm25" else config["embedding_profile"],
        "candidate_pool": config["candidate_pool"] if "hybrid" in config["method"] else "",
        "rrf_k": config["rrf_k"] if "hybrid" in config["method"] else "",
        "rerank_pool": config["rerank_pool"] or "",
    }
    for column in CSV_COLUMNS[8:]:
        value = summary.get(column, "")
        row[column] = round(value, 4) if isinstance(value, float) else value
    return row


def _fmt(value, digits: int = 3) -> str:
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else str(value)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _metric_rows(names: list[str], runs: dict) -> list[list[str]]:
    rows = []
    for name in names:
        summary = runs[name][0]["results"]
        rows.append(
            [
                f"`{name}`",
                _fmt(summary["recall@1"]),
                _fmt(summary["recall@5"]),
                _fmt(summary["recall@10"]),
                f"[{_fmt(summary.get('recall@10_ci_low', 0))}, {_fmt(summary.get('recall@10_ci_high', 0))}]",
                _fmt(summary["mrr"]),
                _fmt(summary["ndcg@10"]),
                _fmt(summary["latency_p50_ms"], 1),
                _fmt(summary["latency_p95_ms"], 1),
            ]
        )
    return rows


METRIC_HEADERS = [
    "config", "R@1", "R@5", "R@10", "R@10 95% CI", "MRR", "nDCG@10",
    "p50 ms", "p95 ms",
]


def command_report(args) -> int:
    registry = build_registry()
    names = completed_runs()
    if not names:
        print("no completed runs found; run `run` first")
        return 1

    runs = {name: load_run(name) for name in names}

    Path(CONFIG.experiments_dir).mkdir(parents=True, exist_ok=True)
    csv_path = Path(CONFIG.experiments_dir) / "results.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for name in sorted(names, key=lambda n: (registry[n].group, n)):
            payload, _ = runs[name]
            writer.writerow(_csv_row(name, payload, payload["results"]))

    sections = [
        "# Experiment results",
        "",
        "Generated by `python -m src.evaluation.run_experiments report`. "
        f"Corpus: {CONFIG.subset_size} recipes from `{CONFIG.dataset_name}` "
        f"({CONFIG.corpus_split}, seed {CONFIG.seed}, revision `{CONFIG.dataset_revision[:7]}`). "
        f"Retrieval depth {args.depth}; metrics over "
        f"{runs[names[0]][0]['results']['num_queries']} constructed queries.",
        "",
    ]

    for group, label in GROUP_LABELS.items():
        group_names = [n for n in names if registry[n].group == group]
        if not group_names:
            continue
        group_names.sort()
        sections += [
            f"## {label}",
            "",
            _markdown_table(METRIC_HEADERS, _metric_rows(group_names, runs)),
            "",
        ]

    # Per-family breakdown for the main comparison: the averages hide that
    # the families stress different retrieval signals.
    main_names = [n for n in names if registry[n].group == "A"]
    if main_names:
        families = sorted(runs[main_names[0]][0]["results"].get("by_family", {}))
        if families:
            rows = []
            for name in sorted(main_names):
                by_family = runs[name][0]["results"]["by_family"]
                rows.append(
                    [f"`{name}`"] + [_fmt(by_family[f]["recall@10"]) for f in families]
                )
            sections += [
                "## Recall@10 by query family (group A)",
                "",
                _markdown_table(["config"] + families, rows),
                "",
            ]

    # Paired bootstrap against the BM25 baseline, on the same queries.
    if "bm25" in runs:
        baseline = per_query_scores(runs["bm25"][1], "recall@10")
        rows = []
        for name in sorted(n for n in names if n != "bm25" and registry[n].group == "A"):
            candidate = per_query_scores(runs[name][1], "recall@10")
            test = paired_bootstrap(baseline, candidate)
            rows.append(
                [
                    f"`{name}` vs `bm25`",
                    _fmt(test["mean_diff"]),
                    f"[{_fmt(test['ci_low'])}, {_fmt(test['ci_high'])}]",
                    _fmt(test["p_value"]),
                ]
            )
        if rows:
            sections += [
                "## Paired bootstrap on Recall@10 (2000 resamples)",
                "",
                _markdown_table(
                    ["comparison", "mean diff", "95% CI", "p"], rows
                ),
                "",
            ]

    report_path = Path(CONFIG.experiments_dir) / "report.md"
    report_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(f"Wrote {csv_path} and {report_path} ({len(names)} configurations)")
    return 0


def command_compare(args) -> int:
    """Paired bootstrap between any two completed runs, on one metric."""
    _, baseline_records = load_run(args.baseline)
    _, candidate_records = load_run(args.candidate)
    test = paired_bootstrap(
        per_query_scores(baseline_records, args.metric),
        per_query_scores(candidate_records, args.metric),
    )
    print(
        f"{args.candidate} vs {args.baseline} on {args.metric}: "
        f"diff={test['mean_diff']:+.4f} "
        f"CI=[{test['ci_low']:+.4f}, {test['ci_high']:+.4f}] "
        f"p={test['p_value']:.4f}"
    )
    return 0


def command_equivalence(args) -> int:
    """
    Check that two runs produce the same ranking.

    Used for the SQL-vs-service fusion ablation: if the two tiers really do
    implement the same RRF, the only thing left to compare is cost, so the
    ranking agreement has to be measured rather than assumed.
    """
    _, left_records = load_run(args.left)
    _, right_records = load_run(args.right)
    by_id = {r.query_id: r for r in right_records}

    identical_top10 = 0
    identical_top1 = 0
    overlap_total = 0.0
    for left in left_records:
        right = by_id[left.query_id]
        left_top, right_top = left.ranked_ids[:10], right.ranked_ids[:10]
        identical_top10 += left_top == right_top
        identical_top1 += left.ranked_ids[:1] == right.ranked_ids[:1]
        overlap_total += len(set(left_top) & set(right_top)) / max(len(left_top), 1)

    n = len(left_records)
    print(f"{args.left} vs {args.right} over {n} queries:")
    print(f"  identical top-1 ranking : {identical_top1}/{n}")
    print(f"  identical top-10 ranking: {identical_top10}/{n}")
    print(f"  mean top-10 overlap     : {overlap_total / max(n, 1):.4f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", default=DEFAULT_QUERY_SET)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute retrieval configurations")
    run_parser.add_argument("--groups", default="", help="Comma-separated ablation groups, e.g. A,C")
    run_parser.add_argument("--configs", default="", help="Comma-separated configuration names")
    run_parser.add_argument("--limit", type=int, default=0, help="Use only the first N queries")
    run_parser.add_argument("--force", action="store_true", help="Re-run configurations already on disk")
    run_parser.set_defaults(func=command_run)

    report_parser = subparsers.add_parser("report", help="Rebuild results.csv and report.md")
    report_parser.set_defaults(func=command_report)

    compare_parser = subparsers.add_parser("compare", help="Paired bootstrap between two runs")
    compare_parser.add_argument("baseline")
    compare_parser.add_argument("candidate")
    compare_parser.add_argument("--metric", default="recall@10")
    compare_parser.set_defaults(func=command_compare)

    equivalence_parser = subparsers.add_parser(
        "equivalence", help="Compare the rankings of two runs position by position"
    )
    equivalence_parser.add_argument("left")
    equivalence_parser.add_argument("right")
    equivalence_parser.set_defaults(func=command_equivalence)

    list_parser = subparsers.add_parser("list", help="List registered configurations")
    list_parser.set_defaults(func=lambda a: _command_list())
    return parser


def _command_list() -> int:
    for name, config in build_registry().items():
        done = "done" if run_path(name).is_file() else "    "
        print(f"[{done}] {config.group}  {name:<22} {config.method:<14} {config.chunk_profile}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
