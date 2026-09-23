"""
Run a retrieval method over the constructed query set and compute metrics.
See docs/08_EVALUATION.md for the protocol: same corpus, same queries,
same ground truth, same K values across all configurations being compared.

Every run keeps a per-query record, not just the aggregate. The records are
what make error analysis (docs/11_ERROR_ANALYSIS.md) and the paired
significance tests in `metrics.paired_bootstrap` possible after the fact,
without re-running any retrieval.
"""

import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Protocol

from src.evaluation.metrics import bootstrap_ci, mrr, ndcg_at_k, recall_at_k
from src.evaluation.queries import EvalQuery

# Every configuration retrieves to the same depth so MRR and nDCG are
# comparable; metrics at smaller K are sliced from the same ranking.
DEFAULT_DEPTH = 50
DEFAULT_K_VALUES = (1, 5, 10)
RECORDED_NAMES = 10  # names/scores kept per query, for error-analysis cards
WARMUP_QUERIES = 3


class SearchFn(Protocol):
    def __call__(self, query: str, top_k: int) -> list:
        ...


class EncodeClock:
    """
    Accumulates query-embedding time so it can be reported apart from the
    SQL/rerank time. BM25 has no encoder and simply leaves this at zero.
    """

    def __init__(self) -> None:
        self.elapsed_ms = 0.0

    def pop(self) -> float:
        elapsed, self.elapsed_ms = self.elapsed_ms, 0.0
        return elapsed


class TimedQueryEncoder:
    """Transparent wrapper around PostgresQueryEncoder that records encode time."""

    def __init__(self, encoder, clock: EncodeClock):
        self._encoder = encoder
        self._clock = clock

    def encode(self, query: str):
        start = time.perf_counter()
        vector = self._encoder.encode(query)
        self._clock.elapsed_ms += (time.perf_counter() - start) * 1000.0
        return vector

    def __getattr__(self, name):
        return getattr(self._encoder, name)


@dataclass
class QueryRecord:
    query_id: int
    family: str
    query_text: str
    source_recipe_idx: int
    relevant_recipe_ids: list[int]
    gold_rank: int | None  # rank of the first relevant hit, None if beyond depth
    ranked_ids: list[int]
    top_names: list[str]
    top_scores: list[float]
    encode_ms: float
    search_ms: float
    base_query_text: str = ""
    substitutions: list[str] = field(default_factory=list)

    @property
    def total_ms(self) -> float:
        return self.encode_ms + self.search_ms


def _first_relevant_rank(ranked_ids: list[int], relevant_ids: set[int]) -> int | None:
    for rank, rid in enumerate(ranked_ids, start=1):
        if rid in relevant_ids:
            return rank
    return None


def run_queries(
    search_fn: SearchFn,
    queries: list[EvalQuery],
    depth: int = DEFAULT_DEPTH,
    clock: EncodeClock | None = None,
) -> list[QueryRecord]:
    """
    Execute every query once at `depth` and capture the ranking plus timing.

    A few warm-up queries run first and are discarded: the first calls pay
    for lazy model loading, connection setup, and cold Postgres caches, which
    would otherwise dominate the latency of whichever configuration runs first.
    """
    for warmup_query in queries[:WARMUP_QUERIES]:
        search_fn(warmup_query.query_text, depth)
    if clock is not None:
        clock.pop()

    records: list[QueryRecord] = []
    for query in queries:
        start = time.perf_counter()
        results = search_fn(query.query_text, depth)
        total_ms = (time.perf_counter() - start) * 1000.0
        encode_ms = clock.pop() if clock is not None else 0.0

        ranked_ids = [r.recipe_idx for r in results]
        relevant_ids = set(query.relevant_recipe_ids)
        records.append(
            QueryRecord(
                query_id=query.query_id,
                family=query.family,
                query_text=query.query_text,
                source_recipe_idx=query.source_recipe_idx,
                relevant_recipe_ids=query.relevant_recipe_ids,
                gold_rank=_first_relevant_rank(ranked_ids, relevant_ids),
                # Ids are kept to the full depth so MRR stays MRR@depth when
                # recomputed from disk; names and scores only for the top hits.
                ranked_ids=ranked_ids,
                top_names=[r.name for r in results[:RECORDED_NAMES]],
                top_scores=[round(float(r.score), 6) for r in results[:RECORDED_NAMES]],
                encode_ms=round(encode_ms, 3),
                search_ms=round(max(total_ms - encode_ms, 0.0), 3),
                base_query_text=query.base_query_text,
                substitutions=query.substitutions,
            )
        )
    return records


def per_query_scores(records: list[QueryRecord], metric: str) -> list[float]:
    """
    Score every query individually under one metric, e.g. "recall@10" or
    "mrr". Used by the paired bootstrap, which needs aligned per-query values
    rather than an average.
    """
    scores = []
    for record in records:
        relevant = set(record.relevant_recipe_ids)
        if metric == "mrr":
            scores.append(mrr(record.ranked_ids, relevant))
        elif metric.startswith("recall@"):
            scores.append(recall_at_k(record.ranked_ids, relevant, int(metric.split("@")[1])))
        elif metric.startswith("ndcg@"):
            scores.append(ndcg_at_k(record.ranked_ids, relevant, int(metric.split("@")[1])))
        else:
            raise ValueError(f"Unknown metric: {metric}")
    return scores


def _metric_block(records: list[QueryRecord], k_values: tuple[int, ...]) -> dict:
    block: dict = {"num_queries": len(records)}
    if not records:
        return block

    for k in k_values:
        block[f"recall@{k}"] = statistics.fmean(per_query_scores(records, f"recall@{k}"))
    block["mrr"] = statistics.fmean(per_query_scores(records, "mrr"))
    block["ndcg@10"] = statistics.fmean(per_query_scores(records, "ndcg@10"))
    return block


def summarize(
    records: list[QueryRecord],
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    depth: int = DEFAULT_DEPTH,
    with_ci: bool = True,
) -> dict:
    """Aggregate metrics, latency percentiles, and a per-family breakdown."""
    summary = _metric_block(records, k_values)
    summary["depth"] = depth

    if not records:
        return summary

    if with_ci:
        # Recall@10 is the headline number, so it is the one that carries an
        # interval in the results table.
        low, high = bootstrap_ci(per_query_scores(records, "recall@10"))
        summary["recall@10_ci_low"] = low
        summary["recall@10_ci_high"] = high

    totals = sorted(r.total_ms for r in records)
    summary["latency_p50_ms"] = statistics.median(totals)
    summary["latency_p95_ms"] = totals[min(len(totals) - 1, int(0.95 * len(totals)))]
    summary["latency_mean_ms"] = statistics.fmean(totals)
    summary["encode_mean_ms"] = statistics.fmean(r.encode_ms for r in records)
    summary["search_mean_ms"] = statistics.fmean(r.search_ms for r in records)

    families = sorted({r.family for r in records})
    summary["by_family"] = {
        family: _metric_block([r for r in records if r.family == family], k_values)
        for family in families
    }
    return summary


def evaluate(
    search_fn: SearchFn,
    queries: list[EvalQuery],
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    depth: int = DEFAULT_DEPTH,
    clock: EncodeClock | None = None,
) -> tuple[dict, list[QueryRecord]]:
    records = run_queries(search_fn, queries, depth=depth, clock=clock)
    return summarize(records, k_values=k_values, depth=depth), records


def records_to_dicts(records: list[QueryRecord]) -> list[dict]:
    return [asdict(r) for r in records]


def records_from_dicts(rows: list[dict]) -> list[QueryRecord]:
    return [QueryRecord(**row) for row in rows]
