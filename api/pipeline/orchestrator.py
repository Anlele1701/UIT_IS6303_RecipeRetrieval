"""One chat turn through M1..M7, as events in the 6.5 SSE format, with a trace row per stage (sườn 3.3).

The flags decide what runs; every preset goes through this one function (CLAUDE.md rule 10). Session state
lives in the DB (session_constraint, chat_message), so a turn can be replayed from the tables alone.
Events: constraints, recipes, token, done. When M7 rewrites the answer, `done.answer` holds the final text
and replaces the streamed one.

A session about a patient (chat_session.patient_id, MV3) with the `profile` flag on adds, before M2: V1 (the tree
from patient_node), V3 (the cached PatientProfile), M1 with the patient schema, V2 (context nodes, at most one
model call), and a `patient_profile` event before `constraints`. A session without a patient runs exactly the M3
calls. A deceased or unknown patient gets no session (PatientUnavailable).
"""

import time
import uuid
from datetime import date
from pathlib import Path
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
from psycopg.types.json import Jsonb

from .. import config
from ..embed import embed_query
from ..patient import baselines, narrative, navigate, profile_store
from ..patient.mapping import build_profile
from ..patient import rules as patient_rules
from ..patient.prompt_view import prompt_view
from . import m4_retrieve as m4
from . import m6_generate as m6
from . import m7_verify as m7
from .flags import MV4_MODES, Flags
from .lexicon import RuntimeLexicon
from .m1_understand import ALLERGEN_WORDS, detect_lang, understand
from .m2_state import merge
from .m3_router import detail_recipe, route
from .m5_postprocess import cards as load_cards
from .m5_postprocess import nutrient_values, recipe_detail, top_recipes
from .schemas import RecipeCard, SessionState, StateItem, Understanding, Verification

ROOT = Path(__file__).resolve().parents[2]
HISTORY_CHARS = 600  # an old assistant answer is cut to this for M1 and M6
LOCKED_VI = "Ràng buộc này đến từ hồ sơ bệnh nhân, không gỡ được qua tin nhắn; cần xác nhận trên giao diện."
LOCKED_EN = "This constraint comes from the patient's record and cannot be lifted by a chat message; confirm it in the interface."


class PatientUnavailable(ValueError):
    """No session for a deceased or unknown patient (Thy, after MV0)."""


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
        self._rules = None  # the patient rule set, loaded on the first patient turn
        self.patient_input = "coded"  # "narrative": the section tables of the C-CDA (eval_patient.py --input, MV4)
        self._chunk_vecs: dict = {}  # P-Vector: (patient, input) -> chunk embeddings

    @property
    def rules(self):
        if self._rules is None:
            self._rules = patient_rules.load_rules()
        return self._rules

    # ---- session storage -------------------------------------------------------------------------------------
    def new_session(self, preset: str = "S", patient_id: str | None = None) -> uuid.UUID:
        if patient_id is not None:
            row = self.conn.execute("SELECT deceased FROM patient WHERE patient_id = %s", [patient_id]).fetchone()
            if row is None:
                raise PatientUnavailable(f"unknown patient {patient_id}")
            if row[0]:
                raise PatientUnavailable(f"patient {patient_id} is deceased: no session")
        sid = uuid.uuid4()
        self.conn.execute("INSERT INTO chat_session (id, preset, patient_id) VALUES (%s, %s, %s)", [sid, preset, patient_id])
        self.conn.commit()
        return sid

    def patient_of(self, sid: uuid.UUID) -> str | None:
        row = self.conn.execute("SELECT patient_id FROM chat_session WHERE id = %s", [sid]).fetchone()
        return row[0] if row else None

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
        for it in [it for it in state.items if (it.type, it.value, it.scope) not in old]:
            self.conn.execute("INSERT INTO session_constraint (session_id, type, value, scope, source_message_id, source, "
                              "evidence) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                              [sid, it.type, it.value, it.scope, source_id, it.source,
                               Jsonb(it.evidence) if it.evidence else None])

    # ---- one turn --------------------------------------------------------------------------------------------
    def run_turn(self, sid: uuid.UUID, message: str, flags: Flags) -> Iterator[Event]:
        start = time.perf_counter()
        tr = Trace()
        prev = self.state(sid) if flags.conv else SessionState()
        history = self.history(sid) if flags.conv else []
        pid = self.patient_of(sid)
        pt = self._patient_start(pid, flags, tr) if pid is not None and flags.profile else None
        self._pt = pt

        with tr.stage("m1") as p:
            if flags.qu and pt:
                u = understand(self.client, self.lex, message, history, prev.constraints(), patient=True)
            elif flags.qu:
                u = understand(self.client, self.lex, message, history, prev.constraints())
            else:
                u = Understanding(lang=detect_lang(message), query_en=message, notes=["qu off: raw message"])
            p.update(u.model_dump())
        if pt:
            pt["lang"] = u.lang
            yield Event("patient_profile", self._patient_select(pt, u, message, flags, tr))
        with tr.stage("m2") as p:
            state = merge(prev, u, conv=flags.conv, profile=pt["profile"]) if pt else merge(prev, u, conv=flags.conv)
            p.update(items=[it.model_dump() for it in state.items], notices=state.notices)
            if pt:  # the trace says plainly when M2 refused to lift a record constraint
                p["refused_removals"] = [n.removeprefix("from_record:") for n in state.notices
                                         if n.startswith("from_record:")]
        with tr.stage("m3") as p:
            path = route(u, state)
            p["route"] = path

        c = state.constraints()
        user_id = self._message(sid, "user", message, u.lang)
        self.conn.execute("UPDATE chat_session SET lang = coalesce(lang, %s) WHERE id = %s", [u.lang, sid])
        self._save_state(sid, state, user_id)
        self.conn.commit()
        event = {"session_id": str(sid), "message_id": user_id, "intent": u.intent, "constraints": c.model_dump(),
                 "notices": state.notices, "route": path, "clarify": u.clarify}
        if pt:  # patient sessions: the record constraints a message tried to lift, said in words for the UI
            event["record_locked"] = [{"constraint": n.removeprefix("from_record:"),
                                       "message": LOCKED_VI if u.lang == "vi" else LOCKED_EN}
                                      for n in state.notices if n.startswith("from_record:")]
        yield Event("constraints", event)

        cards: list[RecipeCard] = []
        shown: list[int] = []
        usage: dict = {}
        answer = ""
        v = Verification(verified=True)
        messages: list[dict] | None = None

        constrained = sorted({*c.nutrient_limits, *c.nutrient_soft})  # empty without a patient
        allowed_numbers = None  # route patient_info: the numbers M7 lets the answer state
        gen_ctx, omitted = m6.GEN_CTX, {}
        if path == "clarify":
            answer = u.clarify or ""
            yield Event("token", answer)
        elif path == "patient_info" and pt:
            views = [prompt_view(n, self.rules) for n in pt["nodes"] if n.node_id in pt["selection"].node_ids]
            views, omitted = m6.fit_views(views)  # newest first, by code: never let Ollama cut the prompt's start
            gen_ctx = m6.PATIENT_INFO_CTX
            block = self._block(pt, state)
            allowed_numbers = m7.number_index(views)  # facts of the nodes read only, units checked (Thy)
            if flags.generate:
                messages = m6.patient_info_messages(message, u.lang, views, block, history)
        elif path == "detail":
            rid = detail_recipe(u, state)
            with tr.stage("m5", {"recipe_id": rid}):
                card, directions = recipe_detail(self.conn, rid, constrained)
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
                if c.nutrient_soft:  # patient soft limits: rank, never filter (ADR-0007)
                    values = nutrient_values(self.conn, list({x.recipe_id for x in chunks}), c.nutrient_soft)
                    ranked = top_recipes(text, chunks, self.scorer, k=self.k, use_rerank=flags.rerank,
                                         soft=c.nutrient_soft, values=values)
                    p["soft"] = sorted(c.nutrient_soft)
                else:
                    ranked = top_recipes(text, chunks, self.scorer, k=self.k, use_rerank=flags.rerank)
                cards = load_cards(self.conn, ranked, constrained) if constrained else load_cards(self.conn, ranked)
                p["recipes"] = [[r.id, r.score] for r in cards]
            shown = [r.id for r in cards]
            yield Event("recipes", [_brief(r) for r in cards])
            if flags.generate and pt:
                messages = m6.answer_messages(message, u.lang, c, cards, history, patient=self._block(pt, state))
            elif flags.generate:
                messages = m6.answer_messages(message, u.lang, c, cards, history)

        if messages is not None:
            with tr.stage("m6", {"messages": len(messages), "num_ctx": gen_ctx, "record_omitted": omitted}) as p:
                t = time.perf_counter()
                parts = []
                for piece in m6.generate(self.client, messages, usage, num_ctx=gen_ctx):
                    if not parts:
                        tr.ms["m6_ttft"] = round((time.perf_counter() - t) * 1000, 1)
                    parts.append(piece)
                    yield Event("token", piece)
                answer = "".join(parts)
                p.update(usage=dict(usage), chars=len(answer))
            if path in {"retrieve", "detail"} or (pt and path == "patient_info"):
                answer, v = self._verify(answer, messages, cards, c, flags, tr, usage,
                                         self._check(pt, c, allowed_numbers), gen_ctx)
            if pt and path in {"retrieve", "detail"} and flags.verify and v.flags:
                answer, v = self._repair(answer, v, cards, c, u.lang, tr)
            if pt and path == "patient_info" and flags.verify and not v.verified:
                # still wrong after the one regeneration: list the values by code; traced, counted in the report
                with tr.stage("fallback", {"kind": "values_answer", "model_flags": list(v.flags)}) as p:
                    answer = m7.values_answer(views, u.lang)
                    p["lines"] = answer.count("\n")
                v = v.model_copy(update={"verified": True, "fallback": True})
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
        done = {"message_id": reply_id, "citations": v.citations, "verified": v.verified,
                "removed": v.removed, "regenerated": v.regenerated, "answer": answer,
                "usage": {"prompt_tokens": usage.get("prompt_tokens", 0),
                          "completion_tokens": usage.get("completion_tokens", 0),
                          "done_reason": usage.get("done_reason")},
                "latency_ms": tr.ms}
        if pt:
            done["flags"] = v.flags
            done["fallback"] = v.fallback  # route patient_info answered by values_answer (code), not the model
        yield Event("done", done)

    def _verify(self, answer, messages, cards, c, flags: Flags, tr: Trace, usage: dict, check=None,
                num_ctx: int = m6.GEN_CTX):
        """M7: always measured (the trace and S-Verify need the numbers); acted on only when flags.verify."""
        with tr.stage("m7", {"applied": flags.verify}) as p:
            v = m7.verify(answer, cards, c, check) if check else m7.verify(answer, cards, c)
            p["first"] = v.model_dump()
            if flags.verify and not v.verified:
                retry = [*messages, {"role": "assistant", "content": answer},
                         {"role": "user", "content": m7.retry_note(v, cards, c)}]
                more: dict = {}
                answer = "".join(m6.generate(self.client, retry, more, num_ctx=num_ctx))
                for key in ("prompt_tokens", "completion_tokens"):
                    usage[key] = usage.get(key, 0) + more.get(key, 0)
                if more.get("done_reason") == "length":  # the regeneration hit GEN_MAX_TOKENS
                    usage["done_reason"] = "length"
                second = m7.verify(answer, cards, c, check) if check else m7.verify(answer, cards, c)
                answer = m7.strip(answer, second.removed, second.bad_nodes)
                v = second.model_copy(update={"regenerated": True, "removed": v.removed + second.removed,
                                              "verified": not second.removed and second.verified})
            p["final"] = v.model_dump()
        return answer, v


    # ---- patient record (MV3) --------------------------------------------------------------------------------
    def _patient_start(self, pid: str, flags: Flags, tr: Trace) -> dict:
        """V1 (the tree) and V3 (the profile), before M1. The MV4 modes read the record per turn: their profile
        is built in _patient_select, after the selection. The narrative input (evaluation only) reads the section
        tables of the C-CDA file and has a model extract the constraints (api/patient/baselines.py)."""
        mode, text_input = flags.profile_mode, self.patient_input == "narrative"
        if text_input and mode == "direct":
            raise ValueError("P-Direct reads coded entries: not applicable to the narrative input")
        with tr.stage("v1") as p:
            if text_input:
                src_dir, src_file = self.conn.execute(
                    "SELECT source_dir, source_file FROM patient WHERE patient_id = %s", [pid]).fetchone()
                nodes, today = narrative.narrative_nodes(ROOT / src_dir / src_file, self.rules.p7)
            else:
                nodes = profile_store.load_nodes(self.conn, pid)
                today = self.conn.execute("SELECT record_date FROM patient WHERE patient_id = %s",
                                          [pid]).fetchone()[0].isoformat()
            p.update(input=self.patient_input, nodes=len(nodes), context_nodes=sum(n.kind == "context" for n in nodes))
        pt = {"patient_id": pid, "nodes": nodes, "today": today, "profile": None, "extract_calls": 0,
              "entities": None, "chunks_read": None}
        if mode in MV4_MODES:
            return pt
        with tr.stage("v3") as p:
            if text_input:  # P-Vectorless on the narrative: the model reads the four fixed sections
                text = "\n\n".join(narrative.as_text(n) for n in nodes if n.kind == "fixed")
                self._from_text(pt, text, narrative.latest_weight(nodes), mode)
            else:
                pt["profile"] = profile_store.load_or_build(self.conn, pid, self.rules, mode)
                pt["entities"] = baselines.coded_entities(nodes)
            self._v3_payload(p, pt)
        return pt

    def _from_text(self, pt: dict, text: str, weight: dict | None, mode: str) -> None:
        ids = baselines.FIXED_ID if self.patient_input == "narrative" else None
        prof, items, calls = baselines.profile_from_text(self.client, text, weight, self.rules, pt["today"],
                                                         pt["patient_id"], mode, ids)
        pt.update(profile=prof, entities=baselines.entities(items), extract_calls=calls, extract_chars=len(text))

    @staticmethod
    def _v3_payload(p: dict, pt: dict) -> None:
        prof = pt["profile"]
        p.update(ruleset_version=prof.ruleset_version, mode=prof.mode, llm_calls=pt["extract_calls"],
                 allergens=sorted(prof.allergens_exclude), ingredients=len(prof.ingredients_exclude),
                 nutrient_limits=sorted(prof.nutrient_limits), nutrient_soft=sorted(prof.nutrient_soft),
                 warnings=len(prof.warnings), unmapped=len(prof.unmapped), entities=pt["entities"])

    def _vector_select(self, pt: dict, message: str) -> tuple[navigate.Selection, str]:
        """P-Vector: chunks of the record text, the top TOP_K by the message (nomic-embed-text). A record's chunk
        embeddings are kept on the Assistant (they do not depend on the message)."""
        key = (pt["patient_id"], self.patient_input)
        table = baselines.chunk_table(baselines.node_lines(pt["nodes"], self.patient_input == "narrative"))
        if not table:
            pt["chunks_read"] = []
            return navigate.Selection([]), ""
        if key not in self._chunk_vecs:
            self._chunk_vecs[key] = baselines._embed(self.client, [f"search_document: {t}" for t, _ in table])
        docs = self._chunk_vecs[key]

        def embed(texts):
            return docs if texts[0].startswith("search_document: ") else baselines._embed(self.client, texts)
        picked = baselines.top_chunks(self.client, [t for t, _ in table], message, embed=embed)
        pt["chunks_read"] = picked
        ids = list(dict.fromkeys(nid for i in picked for nid in table[i][1]))
        return navigate.Selection(ids, chosen=[f"chunk:{i}" for i in picked]), "\n\n".join(table[i][0] for i in picked)

    def _patient_select(self, pt: dict, u: Understanding, message: str, flags: Flags, tr: Trace) -> dict:
        """V2 (and V3 for the MV4 modes), then the patient_profile event (sent before constraints)."""
        needs = u.needs_record_context or u.intent == "patient_info"
        mode, text = flags.profile_mode, None
        with tr.stage("v2") as p:
            if mode == "vector":
                sel, text = self._vector_select(pt, message)
            else:
                sel = navigate.select_nodes(pt["nodes"], message, needs, mode, self.rules, self.client,
                                            today=pt["today"])
            p.update(needs_context=needs, node_ids=sel.node_ids, chosen=sel.chosen, dropped=sel.dropped,
                     llm_calls=sel.llm_calls, fallback=sel.fallback)
        pt["selection"] = sel
        if pt["profile"] is None:  # MV4 modes: the constraints come from what this turn read
            with tr.stage("v3") as p:
                read = [n for n in pt["nodes"] if n.kind == "root" or n.node_id in sel.node_ids]
                if mode == "vector" or self.patient_input == "narrative":
                    if text is None:  # P-Vectorless-Fixed on the narrative: the sections the model picked
                        text = "\n\n".join(narrative.as_text(n) for n in read if n.kind != "root")
                    self._from_text(pt, text, baselines.weight_from_text(text), mode)
                else:  # P-Vectorless-Fixed on the coded entries: the rule tables on the nodes the model picked
                    pt["profile"] = build_profile(read, self.rules, date.fromisoformat(pt["today"]), mode,
                                                  pt["patient_id"])
                    pt["entities"] = baselines.coded_entities(read, set(sel.node_ids))
                self._v3_payload(p, pt)
        prof = pt["profile"]
        return {"patient_id": pt["patient_id"], "allergens_exclude": sorted(prof.allergens_exclude),
                "ingredients_exclude": sorted(prof.ingredients_exclude),
                "nutrient_limits": {k: list(v) for k, v in sorted(prof.nutrient_limits.items())},
                "nutrient_soft": {k: list(v) for k, v in sorted(prof.nutrient_soft.items())},
                "warnings": prof.warnings, "unmapped": prof.unmapped, "ruleset_version": prof.ruleset_version,
                "evidence": {k: [{"node_id": e.node_id, "text": e.text} for e in v]
                             for k, v in sorted(prof.evidence.items())},
                "nodes_read": sel.node_ids, "llm_calls": sel.llm_calls + pt["extract_calls"],
                "input": self.patient_input, "entities": pt["entities"], "chunks_read": pt["chunks_read"],
                "extract_calls": pt["extract_calls"], "extract_chars": pt.get("extract_chars", 0),
                "latency_ms": {k: v for k, v in tr.ms.items() if k in {"v1", "v2", "v3"}}}

    def _block(self, pt: dict, state: SessionState) -> str:
        block = m6.patient_block(pt["profile"], pt["selection"].node_ids)
        kept = [n.split(":", 2)[2] for n in state.notices if n.startswith("from_record:")]
        if kept:  # the user tried to lift a record constraint in words (spec 5.6, M2)
            line = (f"- the user asked to lift {', '.join(kept)}: it comes from the record and stays until "
                    "confirmed in the interface; say so\n")
            block = block.replace("</patient_profile>", line + "</patient_profile>")
        return block

    def _check(self, pt: dict | None, c, numbers: set[float] | None = None) -> m7.PatientCheck | None:
        """M7's patient context. Route patient_info also gets the allowed numbers and the record's condition
        names, masked before the interpretation check (Thy, after MV3)."""
        if not pt:
            return None
        terms: dict[str, list[str]] = {}
        for a in c.allergens_exclude:  # group words too: "hải sản" (lexicon, mode all), "seafood", "đồ biển" (M7)
            vi = [alias for alias, al in self.lex.aliases.items() if a in al.allergens]
            terms[f"allergen:{a}"] = list(dict.fromkeys([*ALLERGEN_WORDS.get(a, []), *vi, *m7.GROUP_WORDS.get(a, [])]))
        for i in c.ingredients_exclude:
            vi = [alias for alias, al in self.lex.aliases.items() if i in al.ingredients]
            terms[f"ingredient:{i}"] = list(dict.fromkeys([i, *vi]))
        names = []
        if numbers is not None:
            for n in pt["nodes"]:
                if n.node_id in {"problems.active", "narrative.problems"}:
                    for f in n.facts:
                        display = f.get("display") or f.get("description") or ""
                        names += [display, display.replace("(disorder)", "").strip()]
        return m7.PatientCheck(node_ids={n.node_id for n in pt["nodes"]}, avoid_terms=terms, numbers=numbers,
                               condition_names=names, lang=pt.get("lang") if numbers is not None else None)

    def _repair(self, answer: str, v, cards, c, lang: str, tr: Trace):
        """A recipe answer still failing the record checks after the one regeneration (Thy, after MV3): drop the
        sentences that suggest something to avoid and check the rest again; if a break remains or no valid
        citation is left, list the fitting Recipes by code. Both are traced as `fallback` (counted in the report)."""
        check = self._check(self._pt, c)
        with tr.stage("fallback", {"model_flags": list(v.flags)}) as p:
            kept = m7.drop_sentences(answer, cards, check.avoid_terms)
            again = m7.verify(kept, cards, c, check)
            if kept and again.verified and again.citations:
                p.update(kind="drop_sentences", dropped_chars=len(answer) - len(kept))
                return kept, again.model_copy(update={"regenerated": True, "fallback": True, "removed": v.removed})
            names = self._allergen_names()
            p.update(kind="recipes_answer", after_drop=list(again.flags), citations_left=len(again.citations))
            listed = m7.recipes_answer(cards, c, lang, names)
            ok = [r.id for r in cards if not m7.violations(r, c)]
            return listed, v.model_copy(update={"verified": True, "fallback": True, "citations": ok})

    def _allergen_names(self) -> dict[str, str]:
        if not hasattr(self, "_names"):
            self._names = dict(self.conn.execute("SELECT code, name_vi FROM allergen").fetchall())
        return self._names


def _brief(r: RecipeCard) -> dict:
    out = {"id": r.id, "title": r.title, "total_minutes": r.total_minutes, "allergens": r.allergens,
           "allergens_may": r.allergens_may, "diet_flags": r.diet_flags, "score": r.score}
    if r.nutrients:  # patient sessions only (MV3)
        out["nutrients"] = r.nutrients
    return out
