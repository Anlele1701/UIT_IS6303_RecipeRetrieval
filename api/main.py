"""Recipe search API.

    uv run uvicorn api.main:app --reload        # then open http://localhost:8000 (UI) or /docs
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from . import allergens, config, dietary_rules, llm, patients, recommend, retrieval, strategies
from .embed import embed_query
from .filters import SearchParams
from .rerank import Reranker


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=8, open=True)
    app.state.http = httpx.Client(timeout=30)
    app.state.reranker = Reranker()
    app.state.rules = dietary_rules.load_rules(config.RULES_PATH)  # a bad rule file stops startup
    app.state.allergens = allergens.load_allergens(config.ALLERGENS_PATH)
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


@app.get("/diet", include_in_schema=False)
def diet_page():
    """The patient recommender page: the same app, which switches on the path."""
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


@app.get("/patients")
def list_patients(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                  q: str | None = Query(None, max_length=100, description="Part of the name"),
                  order: Literal["name", "conditions"] = "name", conn=Depends(get_conn)) -> list[dict]:
    """A page of patient records (Synthea, synthetic) for picking a patient."""
    return patients.list_patients(conn, limit, offset, q, order)


def _profile(conn, patient_id: UUID) -> patients.PatientProfile:
    try:
        return patients.get_profile(conn, patient_id)
    except patients.PatientNotFound:
        raise HTTPException(404, f"no patient {patient_id}") from None


@app.get("/patients/{patient_id}")
def patient_profile(patient_id: UUID, conn=Depends(get_conn)) -> patients.PatientProfile:
    """One patient and their active conditions: a keyed SQL lookup, no embeddings."""
    return _profile(conn, patient_id)


@app.get("/patients/{patient_id}/diet-plan")
def patient_diet_plan(patient_id: UUID, request: Request, conn=Depends(get_conn)) -> dietary_rules.DietPlan:
    """The Filters a patient's active conditions imply, with the evidence behind each.

    Runs only the Dietary Rule Engine: no embedding, reranker or LLM. Pass `filters` to the search
    endpoints as max_<nutrient> to search under them.
    """
    plan = dietary_rules.derive_diet_plan(_profile(conn, patient_id), request.app.state.rules,
                                          dietary_rules.filterable_nutrients(), config.MEALS_PER_DAY)
    return plan


@app.post("/recommend", response_model=recommend.RecommendResponse)
def recommend_for_patient(req: recommend.RecommendRequest, request: Request, conn=Depends(get_conn)):
    """Recipes for a patient and a question, within the limits their conditions imply.

    Runs the Dietary Rule Engine, then Hybrid retrieval under the resulting Filters, re-checks every Recipe
    against its nutrition, and asks the LLM to explain. Filters are never relaxed; the LLM never chooses them.
    """
    problem = strategies.strategy_problem(req.strategy, strategies.registry(conn))
    if problem:
        raise HTTPException(422, [{"type": "value_error", "loc": ["body", "strategy"], "msg": problem}])
    http = request.app.state.http
    try:
        return recommend.recommend(
            conn, req, rules=request.app.state.rules, allergen_book=request.app.state.allergens,
            embed=lambda text: embed_query(http, text),
            scorer=request.app.state.reranker.score, explain=lambda messages: llm.chat(http, messages))
    except patients.PatientNotFound:
        raise HTTPException(404, f"no patient {req.patient_id}") from None
    except httpx.HTTPError as e:  # only the embedder can raise this; llm.chat reports its own failures
        raise HTTPException(503, f"embedding service unavailable: {e}") from e


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
