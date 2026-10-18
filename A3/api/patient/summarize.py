"""V1c: a one-sentence summary for each context node, so V2 can pick nodes from the table of contents alone.

`template` (the default at load time) needs no model. `llm` asks qwen2.5:7b through the cached structured-output
call of the chat pipeline (data/cache/llm.jsonl, seed 42, temperature 0); after two failures the node keeps
its template summary. Both see only the node's prompt view (api/patient/prompt_view.py): a summary goes into the
table of contents a model reads, so it may not name a visit or a condition the allow-lists keep out.
"""

import collections
import json
import re
from dataclasses import replace

import httpx

from .. import config
from ..pipeline.llm import LLMError, chat_json
from .models import PatientNode
from .prompt_view import prompt_view
from .rules import RuleSet

SCHEMA = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
SUMMARY_CTX = 16384  # Ollama keeps half for the prompt
SUMMARY_BUDGET_CHARS = 12000  # the node's facts, newest first (166 of 2,209 nodes run to 183k chars; MV4c)
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


def template_summary(node: PatientNode, rs: RuleSet) -> str:
    view = prompt_view(node, rs, with_summary=False)["facts"]
    n = len(view)
    if node.node_id.startswith("results."):
        return f"{n} lab panel{'s' if n != 1 else ''}: {_counted([_short(f['display']) for f in view])}."
    if node.node_id.startswith("encounters."):
        kinds = [f["class"].replace("_", " ") for f in view]
        return f"{n} encounter{'s' if n != 1 else ''}: {_counted(kinds)}."
    return f"{n} item{'s' if n != 1 else ''}."


def prompt(node: PatientNode, rs: RuleSet) -> list[dict]:
    """The node's prompt view, cut newest-first by code to fit (m6.fit_views): a long node says how many older
    entries it leaves out, so the sentence covers what was shown."""
    from ..pipeline.m6_generate import fit_views
    view = fit_views([prompt_view(node, rs, with_summary=False)], SUMMARY_BUDGET_CHARS)[0][0]
    data = {"title": view["title"], "facts": view["facts"]}
    if view.get("older_entries_not_shown"):
        data["older_entries_not_shown"] = view["older_entries_not_shown"]
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False, sort_keys=True)}]


def llm_summary(client: httpx.Client, node: PatientNode, rs: RuleSet, attempts: int = 2) -> str | None:
    """The model's sentence, or None after `attempts` failures (the caller keeps the template)."""
    for _ in range(attempts):
        try:
            out = chat_json(client, SCHEMA, prompt(node, rs), model=config.QU_MODEL, temperature=0.0,
                            num_ctx=SUMMARY_CTX)
        except (LLMError, httpx.HTTPError):
            continue
        text = str(out.get("summary", "")).strip()
        if text:
            return text
    return None


def summarize(nodes: list[PatientNode], rs: RuleSet, mode: str = "template",
              client: httpx.Client | None = None) -> list[PatientNode]:
    """Fill `summary` on context nodes; other nodes are returned as they are."""
    if mode not in {"template", "llm"}:
        raise ValueError(f"unknown summary mode {mode!r}")
    out = []
    for node in nodes:
        if node.kind != "context":
            out.append(node)
            continue
        text = llm_summary(client, node, rs) if mode == "llm" and client is not None else None
        out.append(replace(node, summary=text or template_summary(node, rs), summary_source="llm" if text else "template"))
    return out
