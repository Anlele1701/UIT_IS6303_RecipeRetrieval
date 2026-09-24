import pytest
from pydantic import ValidationError

from api.filters import SearchParams, where_clause
from api.retrieval import Candidate, rerank, rrf


def cand(cid, score=0.0):
    return Candidate(cid, recipe_id=cid, kind="step", position=1, content=f"T\n{cid}", score=score)


def test_rrf_rewards_chunks_found_by_both_retrievers():
    fused = rrf([cand(1), cand(2), cand(3)], [cand(3), cand(4)], k=60)
    assert [c.chunk_id for c in fused] == [3, 1, 2, 4]
    top = fused[0]
    assert (top.sparse_rank, top.dense_rank) == (3, 1)
    assert top.rrf_score == pytest.approx(1 / 63 + 1 / 61)
    assert fused[-1].sparse_rank is None and fused[-1].dense_rank == 2


def test_rerank_orders_by_scorer_and_records_score():
    out = rerank("q", [cand(1), cand(2)], lambda q, texts: [0.1, 0.9])
    assert [c.chunk_id for c in out] == [2, 1]
    assert out[0].rerank_score == out[0].score == 0.9


def test_where_clause_builds_filters_in_order():
    p = SearchParams(q="shrimp", category=["salad", "main-dish"], kind=["step"],
                     min_rating=4.0, max_total_minutes=30)
    sql, params = where_clause(p)
    assert sql == ("chunker = %s AND category = ANY(%s) AND kind = ANY(%s) "
                   "AND total_minutes <= %s AND rating >= %s")
    assert params == ["semantic-v1", ["salad", "main-dish"], ["step"], 30, 4.0]


def test_unknown_filter_is_rejected():
    with pytest.raises(ValidationError):
        SearchParams(q="x", max_minutes=30)
