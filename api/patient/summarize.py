"""V1c: a one-sentence summary for each context node, so V2 can pick nodes from the table of contents alone.

`template` (the default at load time) needs no model. `llm` asks qwen2.5:7b through the cached structured-output
call of the chat pipeline (data/cache/llm.jsonl, seed 42, temperature 0); after two failures the node keeps
its template summary. The prompt carries only the node's title and facts: they hold no identity (P7).
"""

import collections
import json
import re
from dataclasses import replace

import httpx

from .. import config
from ..pipeline.llm import LLMError, chat_json
from .models import PatientNode

SCHEMA = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
SYSTEM = ("You summarize one section of a patient's medical record for a table of contents. Write ONE short English "
          "sentence (at most 30 words) saying what the section holds, naming the main tests or visit types and any "
          "value that matters for diet (glucose, kidney function, sodium, potassium, cholesterol, iron). "
          "Use only the data given. No advice. Answer with JSON only.")
_TAG = re.compile(r"\s*\((procedure|regime/therapy|environment)\)\s*$")


def _short(display: str | None) -> str:
    """"CBC panel - Blood by Automated count" -> "CBC panel"; drop SNOMED semantic tags."""
    return _TAG.sub("", (display or "?").split(" - ")[0]).strip()


def _counted(names: list[str], top: int = 4) -> str:
    most = collections.Counter(names).most_common()
    parts = [f"{n} {name}" if n > 1 else name for name, n in most[:top]]
    if len(most) > top:
        rest = len(most) - top
        parts.append(f"{rest} other kind{'s' if rest > 1 else ''}")
    return ", ".join(parts)


def template_summary(node: PatientNode) -> str:
    n = len(node.facts)
    if node.node_id.startswith("results."):
        return f"{n} lab panel{'s' if n != 1 else ''}: {_counted([_short(f['display']) for f in node.facts])}."
    if node.node_id.startswith("encounters."):
        return f"{n} encounter{'s' if n != 1 else ''}: {_counted([_short(f['display']) for f in node.facts])}."
    return f"{n} item{'s' if n != 1 else ''}."


def prompt(node: PatientNode) -> list[dict]:
    data = {"title": node.title, "facts": node.facts}
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False, sort_keys=True)}]


def llm_summary(client: httpx.Client, node: PatientNode, attempts: int = 2) -> str | None:
    """The model's sentence, or None after `attempts` failures (the caller keeps the template)."""
    for _ in range(attempts):
        try:
            out = chat_json(client, SCHEMA, prompt(node), model=config.QU_MODEL, temperature=0.0)
        except (LLMError, httpx.HTTPError):
            continue
        text = str(out.get("summary", "")).strip()
        if text:
            return text
    return None


def summarize(nodes: list[PatientNode], mode: str = "template", client: httpx.Client | None = None) -> list[PatientNode]:
    """Fill `summary` on context nodes; other nodes are returned as they are."""
    if mode not in {"template", "llm"}:
        raise ValueError(f"unknown summary mode {mode!r}")
    out = []
    for node in nodes:
        if node.kind != "context":
            out.append(node)
            continue
        text = llm_summary(client, node) if mode == "llm" and client is not None else None
        out.append(replace(node, summary=text or template_summary(node), summary_source="llm" if text else "template"))
    return out
