"""V2: which nodes of a patient tree a turn reads (spec 5.4). Bounded: at most one model call per turn, no loop.

Fixed nodes are always read, by code. Context nodes (results.<year>, encounters.<year>) are read only when M1
says the question needs the history (`needs_record_context`): one structured call picks up to MAX_NODES of them
from the table of contents (node_id, title, summary through prompt_view: no fact, nothing off the allow-lists).
Ids the model makes up are dropped. Two failures -> fixed nodes only, `fallback` in the trace.
`direct` reads coded entries without a model, so it never calls one.
"""

import json
from dataclasses import dataclass, field

import httpx

from .. import config
from ..pipeline.llm import LLMError, chat_json
from .models import PatientNode
from .prompt_view import prompt_view
from .rules import RuleSet

MAX_NODES = 3
SCHEMA = {"type": "object", "required": ["node_ids"],
          "properties": {"node_ids": {"type": "array", "items": {"type": "string"}}}}
SYSTEM = (f"You pick which sections of a patient's record answer a question about the patient's diet. You see only "
          f"the table of contents. Return the node_id of at most {MAX_NODES} sections, most useful first; an empty "
          "list when none helps. Use only node_id values from the table. Answer with JSON only.")


@dataclass
class Selection:
    node_ids: list[str]  # fixed nodes first, then the chosen context nodes
    llm_calls: int = 0
    fallback: bool = False
    chosen: list[str] = field(default_factory=list)  # the context nodes the model picked (kept ones)
    dropped: list[str] = field(default_factory=list)  # ids the model returned that are not in the tree


def toc(nodes: list[PatientNode], rs: RuleSet) -> list[dict]:
    return [{k: v for k, v in prompt_view(n, rs).items() if k in {"node_id", "title", "summary"}} for n in nodes]


def prompt(question: str, candidates: list[PatientNode], rs: RuleSet) -> list[dict]:
    body = {"question": question, "table_of_contents": toc(candidates, rs)}
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(body, ensure_ascii=False)}]


def select_nodes(nodes: list[PatientNode], question: str, needs_context: bool, mode: str, rs: RuleSet,
                 client: httpx.Client | None, attempts: int = 2) -> Selection:
    fixed = [n.node_id for n in nodes if n.kind == "fixed"]
    if mode in {"vectorless_nofixed", "vector"}:
        raise NotImplementedError(f"profile_mode {mode!r} needs api/patient/baselines.py (MV4)")
    context = [n for n in nodes if n.kind == "context"]
    if mode == "direct" or not needs_context or not context:
        return Selection(fixed)
    known = {n.node_id for n in context}
    messages = prompt(question, context, rs)
    calls = 0
    for _ in range(attempts):
        calls += 1  # a cached reply still counts: the turn would have called the model
        try:
            out = chat_json(client, SCHEMA, messages, model=config.QU_MODEL, temperature=0.0)
        except (LLMError, httpx.HTTPError):
            continue
        picked = [str(i) for i in out.get("node_ids", []) if isinstance(i, str)]
        chosen = list(dict.fromkeys(i for i in picked if i in known))[:MAX_NODES]
        return Selection(fixed + chosen, llm_calls=1, chosen=chosen, dropped=[i for i in picked if i not in known])
    return Selection(fixed, llm_calls=calls, fallback=True)
