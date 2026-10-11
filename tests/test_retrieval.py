import pytest
from pydantic import ValidationError

from api import config
from api.filters import SearchParams, where_clause
from api.retrieval import Candidate, fused_candidates, rerank, rrf, sparse


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


def test_where_clause_scopes_to_the_chunking_strategy_then_filters_in_order():
    p = SearchParams(q="shrimp", strategy="fixed", category=["salad", "main-dish"], kind=["step"],
                     min_rating=4.0, max_total_minutes=30)
    sql, params = where_clause(p)
    assert sql == ("strategy = %s AND category = ANY(%s) AND kind = ANY(%s) "
                   "AND total_minutes <= %s AND rating >= %s")
    assert params == ["fixed", ["salad", "main-dish"], ["step"], 30, 4.0]


def test_unknown_filter_is_rejected():
    with pytest.raises(ValidationError):
        SearchParams(q="x", strategy="semantic", max_minutes=30)


class RecordingConn:
    def execute(self, sql, params):
        self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return []


def test_sparse_breaks_score_ties_by_chunk_id_so_order_is_stable():
    conn = RecordingConn()
    sparse(conn, SearchParams(q="shrimp", strategy="semantic"), 10)
    assert "ORDER BY score DESC, id LIMIT" in " ".join(conn.sql.split())


def test_rrf_uses_the_k_it_is_given():
    fused = rrf([cand(1)], [cand(2)], k=10)
    assert fused[0].rrf_score == pytest.approx(1 / 11)


class CannedConn:
    """Answers every Sparse and Dense query with the same 5 Chunks."""

    def execute(self, sql, params):
        return self

    def fetchall(self):
        return [(i, i, "step", 1, f"T\n{i}", 1.0) for i in range(1, 6)]


def test_fused_candidates_cuts_to_the_rerank_top_it_is_given():
    params = SearchParams(q="shrimp", strategy="semantic")
    assert len(fused_candidates(CannedConn(), params, "[0]", rerank_top=2)) == 2


def test_fused_candidates_defaults_to_the_served_settings(monkeypatch):
    monkeypatch.setattr(config, "RERANK_TOP", 3)
    monkeypatch.setattr(config, "RRF_K", 10)
    fused = fused_candidates(CannedConn(), SearchParams(q="shrimp", strategy="semantic"), "[0]")
    assert len(fused) == 3
    assert fused[0].rrf_score == pytest.approx(2 / 11)  # rank 1 in both lists, k read at call time
