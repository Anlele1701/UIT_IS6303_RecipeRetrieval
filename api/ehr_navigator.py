"""Two ways to answer "which conditions is this patient living with now?" from the record document.

    tree   vectorless: the LLM reads a table of contents (section names and sizes, no content), picks the
           sections to read, then lists the active conditions from just those sections.
    dense  baseline with vectors: cut the document into fixed-size pieces, embed them, take the pieces
           closest to the question, and let the LLM list the conditions from those.

Neither is used to decide a Filter. `/recommend` reads the tables; these exist to be measured against them
(scripts/evaluate_ehr_retrieval.py), because the tables are the true answer for a rendered document.

The LLM and the embedder are passed in, so tests run with fakes. `llm(messages)` returns the reply text
and is expected to answer in JSON. Whatever the model names is checked: a code that does not appear in the
text it was shown is dropped and reported, never returned.
"""

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import numpy as np

from . import ehr_document
from .llm import LLMError

LLM = Callable[[list[dict]], str]
QUESTION = "Which medical conditions does the patient currently have? List the active conditions."


@dataclass
class Found:
    code: str
    description: str


@dataclass
class Retrieval:
    method: str  # "tree" | "dense"
    conditions: list[Found] = field(default_factory=list)
    chars_read: int = 0  # characters of the record that the extracting LLM call was shown
    llm_calls: int = 0
    selected: list[str] = field(default_factory=list)  # section ids (tree) or piece numbers (dense)
    rejected: list[str] = field(default_factory=list)  # codes the model named that are not in the text it saw
    error: str | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)

    @property
    def codes(self) -> set[str]:
        return {c.code for c in self.conditions}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def select_messages(toc: str) -> list[dict]:
    return [
        {"role": "system", "content": "You help find information in a long patient record without reading all of it."},
        {"role": "user", "content": (
            "A patient's record is split into sections. This is its table of contents; each line gives the "
            f"section id in brackets, its title and its size:\n\n{toc}\n\n"
            "Which sections must be read to list the medical conditions the patient currently has? "
            "Choose as few sections as possible. "
            'Reply with JSON only, giving each id without the brackets: {"sections": ["<section id>", ...]}')},
    ]


def extract_messages(text: str) -> list[dict]:
    return [
        {"role": "system", "content": "You read part of a patient record and report only what it says."},
        {"role": "user", "content": (
            f"Record text:\n\n{text}\n\n"
            "List every medical condition that the patient currently has, according to this text only. "
            "Do not list conditions that have ended. Copy each SNOMED code exactly as written. "
            'Reply with JSON only: {"conditions": [{"code": "<SNOMED code>", "description": "<name>"}]}')},
    ]


# ---------------------------------------------------------------------------
# Parsing and checking the model's reply
# ---------------------------------------------------------------------------


class BadReply(ValueError):
    pass


def parse_json(reply: str) -> dict:
    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", reply, re.S)  # a model that wrapped the JSON in prose
        try:
            data = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        raise BadReply("the reply is not a JSON object")
    return data


def parse_sections(reply: str, known: list[str], limit: int) -> list[str]:
    """The section ids the model chose that exist, in the order given, without repeats."""
    chosen = parse_json(reply).get("sections")
    if not isinstance(chosen, list):
        raise BadReply("'sections' is not a list")
    # The table of contents shows ids in brackets, and models often copy the brackets: "[active_conditions]".
    cleaned = (x.strip().strip("[]`'\" ").strip() for x in chosen if isinstance(x, str))
    return [s for s in dict.fromkeys(cleaned) if s in known][:limit]


def appears_in(code: str, text: str) -> bool:
    return re.search(rf"(?<![\w.]){re.escape(code)}(?![\w.])", text) is not None


def parse_conditions(reply: str, text: str) -> tuple[list[Found], list[str]]:
    """Conditions whose code is in `text`, and the codes that were not (a model inventing or mistyping one)."""
    items = parse_json(reply).get("conditions")
    if not isinstance(items, list):
        raise BadReply("'conditions' is not a list")
    found: dict[str, Found] = {}
    rejected: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not str(item.get("code", "")).strip():
            continue
        code = str(item["code"]).strip()
        if appears_in(code, text):
            found.setdefault(code, Found(code, str(item.get("description", "")).strip()))
        elif code not in rejected:
            rejected.append(code)
    return list(found.values()), rejected


# ---------------------------------------------------------------------------
# Tree navigation
# ---------------------------------------------------------------------------


def tree_active_conditions(markdown: str, llm: LLM, *, max_sections: int = 4) -> Retrieval:
    out = Retrieval("tree")
    sections = ehr_document.parse_tree(markdown)
    try:
        t = time.perf_counter()
        reply = llm(select_messages(ehr_document.table_of_contents(sections)))
        out.llm_calls += 1
        out.timings_ms["select"] = round((time.perf_counter() - t) * 1000, 1)
        out.selected = parse_sections(reply, [s.section_id for s in sections], max_sections)
        if not out.selected:
            out.error = "the model chose no section that exists"
            return out
        text = ehr_document.read_sections(sections, out.selected)
        out.chars_read = len(text)
        t = time.perf_counter()
        reply = llm(extract_messages(text))
        out.llm_calls += 1
        out.timings_ms["extract"] = round((time.perf_counter() - t) * 1000, 1)
        out.conditions, out.rejected = parse_conditions(reply, text)
    except (LLMError, BadReply) as e:
        out.error = str(e)
    return out


# ---------------------------------------------------------------------------
# Dense baseline
# ---------------------------------------------------------------------------


def chunk_document(markdown: str, max_chars: int = 800) -> list[str]:
    """Fixed-size pieces on line boundaries. Deliberately blind to headings: the usual way to chunk text."""
    pieces, current = [], ""
    for line in markdown.splitlines():
        if current and len(current) + len(line) + 1 > max_chars:
            pieces.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        pieces.append(current)
    return pieces


def closest_pieces(markdown: str, embed_documents: Callable[[list[str]], np.ndarray],
                   embed_query: Callable[[str], np.ndarray], *, k: int = 4,
                   max_chars: int = 800) -> list[tuple[int, str]]:
    """The k pieces closest to the question as (number from 1, text), in document order. No LLM: this is the
    retrieval part alone."""
    pieces = chunk_document(markdown, max_chars)
    sims = embed_documents(pieces) @ embed_query(QUESTION)
    return [(i + 1, pieces[i]) for i in sorted(np.argsort(-sims)[:k].tolist())]


def dense_active_conditions(markdown: str, llm: LLM, embed_documents: Callable[[list[str]], np.ndarray],
                            embed_query: Callable[[str], np.ndarray], *, k: int = 4,
                            max_chars: int = 800) -> Retrieval:
    out = Retrieval("dense")
    try:
        t = time.perf_counter()
        chosen = closest_pieces(markdown, embed_documents, embed_query, k=k, max_chars=max_chars)
        out.timings_ms["embed"] = round((time.perf_counter() - t) * 1000, 1)
        out.selected = [str(n) for n, _ in chosen]
        text = "\n\n".join(piece for _, piece in chosen)
        out.chars_read = len(text)
        t = time.perf_counter()
        reply = llm(extract_messages(text))
        out.llm_calls += 1
        out.timings_ms["extract"] = round((time.perf_counter() - t) * 1000, 1)
        out.conditions, out.rejected = parse_conditions(reply, text)
    except (LLMError, BadReply) as e:
        out.error = str(e)
    except httpx.HTTPError as e:
        out.error = f"embedding service failed: {e}"
    return out
