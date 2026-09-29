"""Recipe search API.

    uv run uvicorn api.main:app --reload        # then open http://localhost:8000 (UI) or /docs
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from . import config, retrieval, strategies
from .embed import embed_query
from .filters import SearchParams
from .rerank import Reranker


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=8, open=True)
    app.state.http = httpx.Client(timeout=30)
    app.state.reranker = Reranker()
    yield
    app.state.http.close()
    app.state.pool.close()


app = FastAPI(title="Recipe Search", lifespan=lifespan,
              description="Sparse (BM25), Dense (vector) and Hybrid (RRF + rerank) retrieval over recipe Chunks.")


class Hit(BaseModel):
    chunk_id: int
    recipe_id: int
    title: str
    kind: str
    position: int
    text: str
    score: float
    sparse_rank: int | None = None
    dense_rank: int | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    method: str
    strategy: str
    query: str
    k: int
    took_ms: float
    results: list[Hit]




def _response(method: str, params, started: float, candidates) -> SearchResponse:
    hits = []
    for c in candidates:
        title, _, text = c.content.partition("\n")
        hits.append(Hit(chunk_id=c.chunk_id, recipe_id=c.recipe_id, title=title, kind=c.kind,
                        position=c.position, text=text, score=c.score, sparse_rank=c.sparse_rank,
                        dense_rank=c.dense_rank, rrf_score=c.rrf_score, rerank_score=c.rerank_score))
    return SearchResponse(method=method, strategy=params.strategy, query=params.q, k=params.k,
                          took_ms=round((time.perf_counter() - started) * 1000, 1), results=hits)


def _embed(request: Request, text: str) -> str:
    try:
        return embed_query(request.app.state.http, text)
    except httpx.HTTPError as e:
        raise HTTPException(503, f"embedding service unavailable: {e}") from e


def get_conn(request: Request):
    with request.app.state.pool.connection() as conn:
        yield conn


def searchable(params: Annotated[SearchParams, Query()], conn=Depends(get_conn)) -> SearchParams:
    """The search params, once their strategy is known to be loaded (422 otherwise)."""
    problem = strategies.strategy_problem(params.strategy, strategies.registry(conn))
    if problem:
        raise HTTPException(422, [{"type": "value_error", "loc": ["query", "strategy"], "msg": problem}])
    return params


Params = Annotated[SearchParams, Depends(searchable)]


STATIC = Path(__file__).parent / "static"  # built by `npm run build` in ui/
app.mount("/assets", StaticFiles(directory=STATIC / "assets", check_dir=False), name="assets")


@app.get("/", include_in_schema=False)
def ui():
    """Demo page comparing the three search endpoints side by side."""
    return FileResponse(STATIC / "index.html")


@app.get("/report", include_in_schema=False)
def report():
    """The Report page: the same app, which switches on the path and reads /report.json."""
    return FileResponse(STATIC / "index.html")


@app.get("/report.json", include_in_schema=False)
def report_bundle():
    """The report bundle, copied from ui/public by `npm run build`."""
    return FileResponse(STATIC / "report.json")


@app.get("/search/sparse", response_model=SearchResponse, response_model_exclude_none=True)
def search_sparse(params: Params, conn=Depends(get_conn)):
    """Sparse retrieval: BM25 over Chunk text."""
    started = time.perf_counter()
    return _response("sparse", params, started, retrieval.sparse(conn, params, params.k))


@app.get("/search/dense", response_model=SearchResponse, response_model_exclude_none=True)
def search_dense(params: Params, request: Request, conn=Depends(get_conn)):
    """Dense retrieval: cosine similarity between query and Chunk embeddings."""
    started = time.perf_counter()
    qvec = _embed(request, params.q)
    return _response("dense", params, started, retrieval.dense(conn, params, qvec, params.k))


@app.get("/search/hybrid", response_model=SearchResponse, response_model_exclude_none=True)
def search_hybrid(params: Params, request: Request, conn=Depends(get_conn)):
    """Hybrid retrieval: sparse + dense fused with RRF, then Reranked by a cross-encoder."""
    started = time.perf_counter()
    qvec = _embed(request, params.q)
    hits = retrieval.hybrid(conn, params, qvec, request.app.state.reranker.score)
    return _response("hybrid", params, started, hits)


@app.get("/strategies")
def list_strategies(conn=Depends(get_conn)) -> list[dict]:
    """Chunking strategies that can be searched, ordered by name."""
    return strategies.loaded(conn)


@app.get("/categories")
def categories(conn=Depends(get_conn)) -> list[str]:
    return [r[0] for r in conn.execute("SELECT name FROM category ORDER BY name").fetchall()]


@app.get("/health")
def health(request: Request):
    status = {"reranker": config.RERANK_MODEL, "reranker_device": request.app.state.reranker.device}
    try:
        with request.app.state.pool.connection() as conn:
            status["chunks"] = strategies.chunk_counts(conn)
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {e}"
    try:
        embed_query(request.app.state.http, "ping")
        status["embedding"] = "ok"
    except Exception as e:
        status["embedding"] = f"error: {e}"
    ok = status["database"] == "ok" and status["embedding"] == "ok"
    if not ok:
        raise HTTPException(503, status)
    return status
