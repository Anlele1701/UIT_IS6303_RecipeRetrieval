"""Sparse, Dense and Hybrid retrieval over Chunks. See CONTEXT.md for the terms."""

from dataclasses import dataclass

import psycopg

from . import config
from .filters import where_clause

COLUMNS = "id, recipe_id, kind, position, content"


@dataclass
class Candidate:
    chunk_id: int
    recipe_id: int
    kind: str
    position: int
    content: str  # "<title>\n<text>", exactly what was embedded and what the reranker reads
    score: float
    sparse_rank: int | None = None
    dense_rank: int | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


def _rows(conn: psycopg.Connection, sql: str, params: list) -> list[Candidate]:
    return [Candidate(*r) for r in conn.execute(sql, params).fetchall()]


def sparse(conn: psycopg.Connection, params, limit: int) -> list[Candidate]:
    """BM25 over chunk content; Filters are applied inside the index."""
    where, wparams = where_clause(params)
    sql = f"""SELECT {COLUMNS}, pdb.score(id) AS score
              FROM chunk WHERE content ||| %s AND {where}
              ORDER BY score DESC LIMIT %s"""
    return _rows(conn, sql, [params.q, *wparams, limit])


def dense(conn: psycopg.Connection, params, qvec: str, limit: int) -> list[Candidate]:
    """Cosine nearest Chunks; score is similarity (1 - distance)."""
    where, wparams = where_clause(params)
    sql = f"""SELECT {COLUMNS}, 1 - (embedding <=> %s::vector) AS score
              FROM chunk WHERE id @@@ pdb.all() AND {where}
              ORDER BY embedding <=> %s::vector LIMIT %s"""
    return _rows(conn, sql, [qvec, *wparams, qvec, limit])


def rrf(sparse_hits: list[Candidate], dense_hits: list[Candidate], k: int = config.RRF_K) -> list[Candidate]:
    """Reciprocal Rank Fusion: score = sum over lists of 1 / (k + rank), rank starting at 1."""
    fused: dict[int, Candidate] = {}
    for hits, field in ((sparse_hits, "sparse_rank"), (dense_hits, "dense_rank")):
        for rank, c in enumerate(hits, 1):
            f = fused.setdefault(c.chunk_id, Candidate(c.chunk_id, c.recipe_id, c.kind, c.position,
                                                       c.content, 0.0, rrf_score=0.0))
            setattr(f, field, rank)
            f.rrf_score += 1 / (k + rank)
    out = sorted(fused.values(), key=lambda c: c.rrf_score, reverse=True)
    for c in out:
        c.score = c.rrf_score
    return out


def rerank(query: str, candidates: list[Candidate], scorer) -> list[Candidate]:
    """Reorder candidates by the reranker's score for (query, chunk content)."""
    for c, s in zip(candidates, scorer(query, [c.content for c in candidates])):
        c.rerank_score = c.score = float(s)
    return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


def hybrid(conn: psycopg.Connection, params, qvec: str, scorer) -> list[Candidate]:
    n = config.HYBRID_CANDIDATES
    fused = rrf(sparse(conn, params, n), dense(conn, params, qvec, n))
    return rerank(params.q, fused[:config.RERANK_TOP], scorer)[:params.k]
