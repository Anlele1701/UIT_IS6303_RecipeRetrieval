"""V2: which nodes of a patient tree a turn reads (spec 5.4). Bounded: at most one model call per turn, no loop.

Fixed nodes are always read, by code. Context nodes (results.<year>, encounters.<year>) are read only when M1
says the question needs the history (`needs_record_context`): one structured call picks up to MAX_NODES of them
from the table of contents (node_id, title, summary through prompt_view: no fact, nothing off the allow-lists).
Ids the model makes up are dropped. Two failures -> fixed nodes only, `fallback` in the trace.
`direct` reads coded entries without a model, so it never calls one. `vectorless_nofixed` (P-Vectorless-Fixed,
MV4) reads no node by default: the model picks among every node, fixed ones included, up to MAX_NODES_ALL.
`vector` (P-Vector) does not walk the tree at all: api/patient/baselines.py retrieves chunks instead.
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
MAX_NODES_ALL = 6  # vectorless_nofixed: the fixed four plus two context nodes
SCHEMA = {"type": "object", "required": ["node_ids"],
          "properties": {"node_ids": {"type": "array", "items": {"type": "string"}}}}
SYSTEM = ("You pick which sections of a patient's record answer a question about the patient's diet. You see only "
          "the table of contents. Return the node_id of at most {cap} sections, most useful first; an empty "
          "list when none helps. Use only node_id values from the table. Answer with JSON only.")
NOFIXED_NOTE = (" Only the sections you pick are read: the patient's food allergies, conditions and medications "
                "are known only if you pick the sections that hold them.")  # P-Vectorless-Fixed: a fair baseline


@dataclass
class Selection:
    node_ids: list[str]  # fixed nodes first, then the chosen context nodes
    llm_calls: int = 0
    fallback: bool = False
    chosen: list[str] = field(default_factory=list)  # the context nodes the model picked (kept ones)
    dropped: list[str] = field(default_factory=list)  # ids the model returned that are not in the tree


def toc(nodes: list[PatientNode], rs: RuleSet) -> list[dict]:
    return [{k: v for k, v in prompt_view(n, rs).items() if k in {"node_id", "title", "summary"}} for n in nodes]


def prompt(question: str, candidates: list[PatientNode], rs: RuleSet, cap: int = MAX_NODES,
           nofixed: bool = False) -> list[dict]:
    body = {"question": question, "table_of_contents": toc(candidates, rs)}
    return [{"role": "system", "content": SYSTEM.format(cap=cap) + (NOFIXED_NOTE if nofixed else "")},
            {"role": "user", "content": json.dumps(body, ensure_ascii=False)}]


def select_nodes(nodes: list[PatientNode], question: str, needs_context: bool, mode: str, rs: RuleSet,
                 client: httpx.Client | None, attempts: int = 2) -> Selection:
    fixed = [n.node_id for n in nodes if n.kind == "fixed"]
    if mode == "vector":
        raise ValueError("profile_mode 'vector' retrieves chunks (api/patient/baselines.py), it does not walk the tree")
    if mode == "vectorless_nofixed":  # no node is read for free: the model picks them all, whatever the question
        candidates, cap, base = [n for n in nodes if n.kind in {"fixed", "context"}], MAX_NODES_ALL, []
    else:
        candidates, cap, base = [n for n in nodes if n.kind == "context"], MAX_NODES, fixed
        if mode == "direct" or not needs_context or not candidates:
            return Selection(fixed)
    known = {n.node_id for n in candidates}
    messages = prompt(question, candidates, rs, cap, mode == "vectorless_nofixed")
    calls = 0
    for _ in range(attempts):
        calls += 1  # a cached reply still counts: the turn would have called the model
        try:
            out = chat_json(client, SCHEMA, messages, model=config.QU_MODEL, temperature=0.0)
        except (LLMError, httpx.HTTPError):
            continue
        picked = [str(i) for i in out.get("node_ids", []) if isinstance(i, str)]
        chosen = list(dict.fromkeys(i for i in picked if i in known))[:cap]
        return Selection(base + chosen, llm_calls=calls, chosen=chosen, dropped=[i for i in picked if i not in known])
    return Selection(base, llm_calls=calls, fallback=True)
