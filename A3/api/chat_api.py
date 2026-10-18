"""Chat endpoints (M4; contract in docs/plan/A3_ke_hoach_build.md section 6.5). They only call the pipeline.

    POST  /chat                                         one turn, streamed as SSE
    GET   /sessions/{id}                                messages, constraints in force (with ids), lifts, groups
    PATCH /sessions/{id}                                change the preset
    PATCH /chat/{session}/constraints/{constraint_id}   remove a constraint (a record one needs confirm=true)
    GET   /recipes/{id}                                 one Recipe: card and directions
    POST  /feedback                                     thumbs up / down on an answer

Each request gets an Assistant on a pooled connection that stays open until the stream ends (a yield dependency
may close before a StreamingResponse finishes), from the `assistant_factory` dependency tests override.
"""

import json
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .pipeline import orchestrator as orch
from .pipeline.flags import PRESETS, preset
from .pipeline.lexicon import RuntimeLexicon
from .pipeline.m5_postprocess import recipe_detail

router = APIRouter(tags=["chat"])
Factory = Callable[[], AbstractContextManager[orch.Assistant]]


def assistant_factory(request: Request) -> Factory:
    st = request.app.state

    @contextmanager
    def make() -> Iterator[orch.Assistant]:
        with st.pool.connection() as conn:
            if st.lex is None:
                st.lex = RuntimeLexicon.load(conn)
            yield orch.Assistant(conn, st.llm, st.reranker.score, st.lex)
    return make


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _uuid(text: str) -> uuid.UUID:
    try:
        return uuid.UUID(text)
    except ValueError as e:
        raise HTTPException(404, f"unknown session {text}") from e


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    preset: str | None = None  # a new session only; default S, or P-Vectorless with a patient
    patient_id: str | None = None  # a new session only


@router.post("/chat")
def chat(body: ChatRequest, make: Factory = Depends(assistant_factory)):
    """One turn as SSE: patient_profile? constraints recipes? token* done (or error)."""
    name = body.preset or ("P-Vectorless" if body.patient_id else "S")
    if name not in PRESETS:
        raise HTTPException(422, f"unknown preset {name!r}; known: {', '.join(PRESETS)}")
    with make() as bot:  # checks before the stream starts, so they can still be HTTP errors
        if body.session_id is None:
            try:
                sid = bot.new_session(name, body.patient_id)
            except orch.PatientUnavailable as e:
                raise HTTPException(409, str(e)) from e
        else:
            sid = _uuid(body.session_id)
            row = bot.conn.execute("SELECT preset FROM chat_session WHERE id = %s", [sid]).fetchone()
            if row is None:
                raise HTTPException(404, f"unknown session {sid}")
            name = row[0]

    def stream() -> Iterator[str]:
        with make() as bot:
            try:
                for e in bot.run_turn(sid, body.message, preset(name)):
                    yield sse(e.type, e.data)
            except Exception as e:  # Ollama down, a prompt too long...: the client gets an event, not a cut stream
                bot.conn.rollback()
                yield sse("error", {"session_id": str(sid), "error": type(e).__name__, "detail": str(e)[:300]})
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Session-Id": str(sid)})


@router.get("/sessions/{session_id}")
def get_session(session_id: str, make: Factory = Depends(assistant_factory)) -> dict:
    with make() as bot:
        view = bot.session_view(_uuid(session_id))
    if view is None:
        raise HTTPException(404, f"unknown session {session_id}")
    return view


class SessionPatch(BaseModel):
    preset: str


@router.patch("/sessions/{session_id}")
def patch_session(session_id: str, body: SessionPatch, make: Factory = Depends(assistant_factory)) -> dict:
    sid = _uuid(session_id)
    with make() as bot:
        if bot.session_view(sid) is None:
            raise HTTPException(404, f"unknown session {session_id}")
        try:
            bot.set_preset(sid, body.preset)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        return bot.session_view(sid)


class ConstraintPatch(BaseModel):
    action: Literal["remove"] = "remove"
    confirm: bool = False
    reason: str | None = Field(default=None, max_length=500)


@router.patch("/chat/{session_id}/constraints/{constraint_id:path}")
def patch_constraint(session_id: str, constraint_id: str, body: ConstraintPatch,
                     make: Factory = Depends(assistant_factory)) -> dict:
    sid = _uuid(session_id)
    with make() as bot:
        if bot.session_view(sid) is None:
            raise HTTPException(404, f"unknown session {session_id}")
        try:
            return bot.remove_constraint(sid, constraint_id, body.confirm, body.reason)
        except orch.RecordLiftRefused as e:
            raise HTTPException(409, str(e)) from e
        except LookupError as e:
            raise HTTPException(404, str(e)) from e


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, make: Factory = Depends(assistant_factory)) -> dict:
    with make() as bot:
        card, directions = recipe_detail(bot.conn, recipe_id)
    if card is None:
        raise HTTPException(404, f"unknown recipe {recipe_id}")
    return {**card.model_dump(exclude={"ingredients_norm", "score", "nutrients"}), "directions": directions}


class Feedback(BaseModel):
    message_id: int
    rating: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/feedback", status_code=201)
def post_feedback(body: Feedback, make: Factory = Depends(assistant_factory)) -> dict:
    with make() as bot:
        role = bot.conn.execute("SELECT role FROM chat_message WHERE id = %s", [body.message_id]).fetchone()
        if role is None or role[0] != "assistant":
            raise HTTPException(404, f"no assistant message {body.message_id}")
        fid = bot.conn.execute("INSERT INTO feedback (message_id, rating, comment) VALUES (%s, %s, %s) RETURNING id",
                               [body.message_id, body.rating, body.comment]).fetchone()[0]
        bot.conn.commit()
    return {"id": fid}
