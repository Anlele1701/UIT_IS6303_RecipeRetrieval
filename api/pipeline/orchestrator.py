"""One chat turn through M1..M7, as events in the 6.5 SSE format, with a trace row per stage (sườn 3.3).

The flags decide what runs; every preset goes through this one function (CLAUDE.md rule 10). Session state
lives in the DB (session_constraint, chat_message), so a turn can be replayed from the tables alone.
Events: constraints, recipes, token, done. When M7 rewrites the answer, `done.answer` holds the final text
and replaces the streamed one.
"""

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
from psycopg.types.json import Jsonb

from .. import config
from ..embed import embed_query
from . import m4_retrieve as m4
from . import m6_generate as m6
from . import m7_verify as m7
from .flags import Flags
from .lexicon import RuntimeLexicon
from .m1_understand import detect_lang, understand
from .m2_state import merge
from .m3_router import detail_recipe, route
from .m5_postprocess import cards as load_cards
from .m5_postprocess import recipe_detail, top_recipes
from .schemas import RecipeCard, SessionState, StateItem, Understanding, Verification

HISTORY_CHARS = 600  # an old assistant answer is cut to this for M1 and M6


@dataclass
class Event:
    type: str  # constraints | recipes | token | done
    data: Any


class Trace:
    def __init__(self):
        self.rows: list[tuple[str, dict, float]] = []
        self.ms: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str, payload: dict | None = None):
        p = payload if payload is not None else {}
        t = time.perf_counter()
        try:
            yield p
        finally:
            ms = round((time.perf_counter() - t) * 1000, 1)
            self.ms[name] = self.ms.get(name, 0) + ms
            self.rows.append((name, p, ms))

    def watch(self, prefix: str):
        """For m4_retrieve.search: sub-stage timings go into the m4 payload, not new trace rows."""
        sub: dict[str, float] = {}

        @contextmanager
        def timed(stage: str):
            t = time.perf_counter()
            yield
            sub[f"{prefix}_{stage}"] = round((time.perf_counter() - t) * 1000, 1)
        return timed, sub


class Assistant:
    def __init__(self, conn: psycopg.Connection, client: httpx.Client, scorer, lex: RuntimeLexicon | None = None,
                 strategy: str = config.CHAT_STRATEGY, k: int = config.CONTEXT_RECIPES):
        self.conn, self.client, self.scorer = conn, client, scorer
        self.lex = lex or RuntimeLexicon.load(conn)
        self.strategy, self.k = strategy, k

    # ---- session storage -------------------------------------------------------------------------------------
    def new_session(self, preset: str = "S") -> uuid.UUID:
        sid = uuid.uuid4()
        self.conn.execute("INSERT INTO chat_session (id, preset) VALUES (%s, %s)", [sid, preset])
        self.conn.commit()
        return sid

    def state(self, sid: uuid.UUID) -> SessionState:
        items = [StateItem(type=t, value=v, scope=s) for t, v, s in self.conn.execute(
            "SELECT type, value, scope FROM session_constraint WHERE session_id = %s AND active ORDER BY id",
            [sid]).fetchall()]
        last = self.conn.execute("SELECT recipe_ids FROM chat_message WHERE session_id = %s AND role = 'assistant' "
                                 "AND cardinality(recipe_ids) > 0 ORDER BY id DESC LIMIT 1", [sid]).fetchone()
        return SessionState(items=items, last_recipe_ids=last[0] if last else [])

    def history(self, sid: uuid.UUID, turns: int = config.HISTORY_TURNS) -> list[dict]:
        rows = self.conn.execute("SELECT role, content FROM chat_message WHERE session_id = %s ORDER BY id DESC "
                                 "LIMIT %s", [sid, 2 * turns]).fetchall()
        return [{"role": r, "content": c[:HISTORY_CHARS]} for r, c in reversed(rows)]

    def _message(self, sid, role: str, content: str, lang: str, recipe_ids: list[int] | None = None) -> int:
        return self.conn.execute("INSERT INTO chat_message (session_id, role, content, lang, recipe_ids) "
                                 "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                 [sid, role, content, lang, recipe_ids or []]).fetchone()[0]

    def _save_state(self, sid, state: SessionState, source_id: int) -> None:
        """Keep rows that still hold, deactivate the ones M2 dropped, add the new ones (with their message)."""
        now = {(it.type, it.value, it.scope) for it in state.items}
        old = {(t, v, s): i for i, t, v, s in self.conn.execute(
            "SELECT id, type, value, scope FROM session_constraint WHERE session_id = %s AND active", [sid])}
        gone = [i for key, i in old.items() if key not in now]
        if gone:
            self.conn.execute("UPDATE session_constraint SET active = false WHERE id = ANY(%s)", [gone])
        for t, v, s in [(it.type, it.value, it.scope) for it in state.items if (it.type, it.value, it.scope) not in old]:
            self.conn.execute("INSERT INTO session_constraint (session_id, type, value, scope, source_message_id) "
                              "VALUES (%s, %s, %s, %s, %s)", [sid, t, v, s, source_id])

    # ---- one turn --------------------------------------------------------------------------------------------
    def run_turn(self, sid: uuid.UUID, message: str, flags: Flags) -> Iterator[Event]:
        start = time.perf_counter()
        tr = Trace()
        prev = self.state(sid) if flags.conv else SessionState()
        history = self.history(sid) if flags.conv else []

        with tr.stage("m1") as p:
            if flags.qu:
                u = understand(self.client, self.lex, message, history, prev.constraints())
            else:
                u = Understanding(lang=detect_lang(message), query_en=message, notes=["qu off: raw message"])
            p.update(u.model_dump())
        with tr.stage("m2") as p:
            state = merge(prev, u, conv=flags.conv)
            p.update(items=[it.model_dump() for it in state.items], notices=state.notices)
        with tr.stage("m3") as p:
            path = route(u, state)
            p["route"] = path

        c = state.constraints()
        user_id = self._message(sid, "user", message, u.lang)
        self.conn.execute("UPDATE chat_session SET lang = coalesce(lang, %s) WHERE id = %s", [u.lang, sid])
        self._save_state(sid, state, user_id)
        self.conn.commit()
        yield Event("constraints", {"session_id": str(sid), "message_id": user_id, "intent": u.intent,
                                    "constraints": c.model_dump(), "notices": state.notices, "route": path,
                                    "clarify": u.clarify})

        cards: list[RecipeCard] = []
        shown: list[int] = []
        usage: dict = {}
        answer = ""
        v = Verification(verified=True)
        messages: list[dict] | None = None

        if path == "clarify":
            answer = u.clarify or ""
            yield Event("token", answer)
        elif path == "detail":
            rid = detail_recipe(u, state)
            with tr.stage("m5", {"recipe_id": rid}):
                card, directions = recipe_detail(self.conn, rid)
            cards = [card] if card else []
            yield Event("recipes", [_brief(r) for r in cards])
            if card and flags.generate:
                messages = m6.detail_messages(message, u.lang, card, directions)
        elif path == "chat":
            if flags.generate:
                messages = m6.chat_messages(message, u.lang)
        else:
            text = m4.query_text(u.query_en or message, c, flags.filter)
            with tr.stage("m4", {"query": text, "filter": flags.filter, "norm": flags.norm,
                                 "unknown_strict": flags.unknown_strict}) as p:
                t = time.perf_counter()
                qvec = embed_query(self.client, text)
                timed, sub = tr.watch("m4")
                sub["m4_embed"] = round((time.perf_counter() - t) * 1000, 1)
                chunks = m4.search(self.conn, text, qvec, c, filter_on=flags.filter, norm=flags.norm,
                                   unknown_strict=flags.unknown_strict, strategy=self.strategy, watch=timed)
                p.update(chunks=len(chunks), recipes=len({x.recipe_id for x in chunks}), timings=sub)
            with tr.stage("m5", {"rerank": flags.rerank}) as p:
                ranked = top_recipes(text, chunks, self.scorer, k=self.k, use_rerank=flags.rerank)
                cards = load_cards(self.conn, ranked)
                p["recipes"] = [[r.id, r.score] for r in cards]
            shown = [r.id for r in cards]
            yield Event("recipes", [_brief(r) for r in cards])
            if flags.generate:
                messages = m6.answer_messages(message, u.lang, c, cards, history)

        if messages is not None:
            with tr.stage("m6", {"messages": len(messages)}) as p:
                t = time.perf_counter()
                parts = []
                for piece in m6.generate(self.client, messages, usage):
                    if not parts:
                        tr.ms["m6_ttft"] = round((time.perf_counter() - t) * 1000, 1)
                    parts.append(piece)
                    yield Event("token", piece)
                answer = "".join(parts)
                p.update(usage=dict(usage), chars=len(answer))
            if path in {"retrieve", "detail"}:
                answer, v = self._verify(answer, messages, cards, c, flags, tr, usage)
        elif path == "chat":
            answer = ("Mình chỉ giúp tìm công thức nấu ăn." if u.lang == "vi"
                      else "I can only help with recipes and cooking.")
            yield Event("token", answer)

        reply_id = self._message(sid, "assistant", answer, u.lang, shown)
        if "m6" in tr.ms:
            tr.ms["m6_total"] = tr.ms["m6"]
        tr.ms["total"] = round((time.perf_counter() - start) * 1000, 1)
        for stage, payload, ms in tr.rows:
            self.conn.execute("INSERT INTO retrieval_trace (message_id, stage, payload, latency_ms) "
                              "VALUES (%s, %s, %s, %s)", [reply_id, stage, Jsonb(payload), ms])
        self.conn.commit()
        yield Event("done", {"message_id": reply_id, "citations": v.citations, "verified": v.verified,
                             "removed": v.removed, "regenerated": v.regenerated, "answer": answer,
                             "usage": {"prompt_tokens": usage.get("prompt_tokens", 0),
                                       "completion_tokens": usage.get("completion_tokens", 0)},
                             "latency_ms": tr.ms})

    def _verify(self, answer, messages, cards, c, flags: Flags, tr: Trace, usage: dict):
        """M7: always measured (the trace and S-Verify need the numbers); acted on only when flags.verify."""
        with tr.stage("m7", {"applied": flags.verify}) as p:
            v = m7.verify(answer, cards, c)
            p["first"] = v.model_dump()
            if flags.verify and not v.verified:
                retry = [*messages, {"role": "assistant", "content": answer},
                         {"role": "user", "content": m7.retry_note(v, cards, c)}]
                more: dict = {}
                answer = "".join(m6.generate(self.client, retry, more))
                for key in ("prompt_tokens", "completion_tokens"):
                    usage[key] = usage.get(key, 0) + more.get(key, 0)
                second = m7.verify(answer, cards, c)
                answer = m7.strip(answer, second.removed)
                v = second.model_copy(update={"regenerated": True, "removed": v.removed + second.removed,
                                              "verified": not second.removed and second.verified})
            p["final"] = v.model_dump()
        return answer, v


def _brief(r: RecipeCard) -> dict:
    return {"id": r.id, "title": r.title, "total_minutes": r.total_minutes, "allergens": r.allergens,
            "allergens_may": r.allergens_may, "diet_flags": r.diet_flags, "score": r.score}
