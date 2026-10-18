"""The comparison systems of RQ5 (spec 5.8, 6): constraints read by a model from text instead of by code.

- extract(): qwen2.5:7b fills a JSON schema (food allergies in force, active conditions, medications taken) from
  record text, copying each item's description. One structured call, cached (data/cache/llm.jsonl, seed 42).
- profile_from_items(): the extracted descriptions -> coded-like fixed nodes (via a display -> code terminology
  built from every record file, any status: a dictionary, not this patient's answer) -> mapping.build_profile.
- P-Vector: the record text cut into chunks of CHUNK_LINES lines, embedded with nomic-embed-text, the top K by the
  user's message, then extract() on them.
Only the evaluation uses this module (scripts/eval_patient.py); production reads the coded entries.
"""

import json
import re
from dataclasses import replace
from datetime import date
from functools import cache
from pathlib import Path

import httpx
import numpy as np

from .. import config
from ..pipeline.llm import LLMError, chat_json
from . import ccda
from .mapping import build_profile
from .models import PatientNode, PatientProfile
from .rules import RuleSet

ROOT = Path(__file__).resolve().parents[2]
CHUNK_LINES = 8
TOP_K = 6
EXTRACT_CTX = 16384  # the four fixed narrative sections run to ~12k characters; 4096 would cut the prompt
SCHEMA = {"type": "object", "required": ["food_allergies", "conditions", "medications"],
          "properties": {k: {"type": "array", "items": {"type": "string"}}
                         for k in ("food_allergies", "conditions", "medications")}}
SYSTEM = """You read parts of one patient's medical record, as of {today}. List, copying each item's description
exactly as written:
- food_allergies: allergies to a FOOD that are still in force (not drugs, pollen, animals, mold, latex, insects);
- conditions: disorders that are still active (no end date, or an end date after {today}); not findings or situations;
- medications: medications still taken (no end date, or an end date on or after {today}).
Use only the text given. Answer with JSON only."""
FIXED_ID = {"allergies": "narrative.allergies", "problems.active": "narrative.problems",
            "meds.active": "narrative.medications", "vitals.latest": "narrative.vitals"}


def _key(text: str) -> str:
    """Lowercased, spaces squashed, a trailing semantic tag dropped: "Essential hypertension (disorder)" and
    "essential hypertension" are one key."""
    t = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return re.sub(r"\s*\((disorder|finding|situation|substance|food|product|organism|qualifier value)\)$", "", t)


@cache
def terminology() -> dict[str, dict[str, str]]:
    """display (lowercased) -> code, for allergy substances, problems and medications, from every record file of
    both sources and every status. A code dictionary for the text baselines; it says nothing about who has what."""
    term: dict[str, dict[str, str]] = {"allergy": {}, "problem": {}, "medication": {}}
    for folder in (config.PATIENT_DATA_DIR, config.PATIENT_GENERATED_DIR):
        for path in sorted((ROOT / folder).glob("*.xml")):
            doc = ccda.parse(path)
            secs = ccda.sections(doc)
            for s in secs.get(ccda.ALLERGIES, []):
                for a in ccda.allergies(s):
                    if a.substance_display and a.substance_code:
                        term["allergy"][_key(a.substance_display)] = a.substance_code
            for s in secs.get(ccda.PROBLEMS, []):
                for p in ccda.problems(s):
                    if p.display and p.code:
                        term["problem"][_key(p.display)] = p.code
            for s in secs.get(ccda.MEDICATIONS, []):
                for m in ccda.medications(s, date.max):
                    if m.display and m.code:
                        term["medication"][_key(m.display)] = m.code
    return term


def extract(client: httpx.Client, text: str, today: str) -> tuple[dict[str, list[str]], int]:
    """The model's lists and the number of calls made (a failed call counts; two failures give empty lists).
    No text (nothing was read) -> no call: a model asked about nothing makes items up."""
    if not text.strip():
        return {k: [] for k in SCHEMA["required"]}, 0
    messages = [{"role": "system", "content": SYSTEM.format(today=today)}, {"role": "user", "content": text}]
    for attempt in range(1, 3):
        try:
            out = chat_json(client, SCHEMA, messages, model=config.QU_MODEL, temperature=0.0, num_ctx=EXTRACT_CTX)
            return {k: [str(x) for x in out.get(k, []) if str(x).strip()] for k in SCHEMA["required"]}, attempt
        except (LLMError, httpx.HTTPError):
            continue
    return {k: [] for k in SCHEMA["required"]}, 2


def entities(items: dict[str, list[str]]) -> dict[str, list[str]]:
    """Extracted descriptions -> codes; a description the terminology lacks stays as "?<text>" (a false positive)."""
    term = terminology()

    def codes(kind, xs):
        return sorted({term[kind].get(_key(x), f"?{_key(x)}") for x in xs})
    return {"food_allergy_substances": codes("allergy", items["food_allergies"]),
            "conditions": codes("problem", items["conditions"]), "medications": codes("medication", items["medications"])}


def coded_entities(nodes: list[PatientNode], only: set[str] | None = None) -> dict[str, list[str]]:
    """What the coded fixed nodes hold (all of them, or only the ones a selection read)."""
    facts = {n.node_id: n.facts for n in nodes if only is None or n.node_id in only}
    return {"food_allergy_substances": sorted({a["substance_code"] for a in facts.get("allergies", [])
                                               if a.get("kind_code") == ccda.FOOD_ALLERGY and a.get("substance_code")}),
            "conditions": sorted({p["code"] for p in facts.get("problems.active", []) if p.get("code")}),
            "medications": sorted({m["code"] for m in facts.get("meds.active", []) if m.get("code")})}


def profile_from_items(items: dict[str, list[str]], weight: dict | None, rs: RuleSet, today: str, patient_id: str,
                       mode: str, evidence_ids: dict[str, str] | None = None) -> PatientProfile:
    """Extracted lists -> the fixed nodes mapping.py reads -> PatientProfile; evidence points at the nodes the text
    came from (evidence_ids: fixed node id -> the node the model read)."""
    root = f"patient:{patient_id}"

    def node(nid, facts):
        return PatientNode(nid, root, "fixed", nid, None, facts, [])
    nodes = [PatientNode(root, None, "root", "Patient", None, [], []),
             node("allergies", [{"entry_id": "", "kind_code": ccda.FOOD_ALLERGY, "substance_code": c, "substance": d,
                                 "reactions": [], "severity": None}
                                for d, c in zip(items["food_allergies"], ent_codes(items["food_allergies"], "allergy"))]),
             node("problems.active", [{"entry_id": "", "code": c, "display": d}
                                      for d, c in zip(items["conditions"], ent_codes(items["conditions"], "problem"))]),
             node("meds.active", [{"entry_id": "", "code": c, "display": d}
                                  for d, c in zip(items["medications"], ent_codes(items["medications"], "medication"))]),
             node("vitals.latest", [weight] if weight else [])]
    profile = build_profile(nodes, rs, date.fromisoformat(today), mode, patient_id)
    ids = evidence_ids or {}
    if not ids:
        return profile
    remapped = {k: [replace(e, node_id=ids.get(e.node_id, e.node_id)) for e in v] for k, v in profile.evidence.items()}
    return replace(profile, evidence=remapped)


def ent_codes(descriptions: list[str], kind: str) -> list[str]:
    term = terminology()[kind]
    return [term.get(_key(d), "") for d in descriptions]


# ---- P-Vector -------------------------------------------------------------------------------------------------

def coded_lines(nodes: list[PatientNode]) -> list[str]:
    """The coded nodes as text lines (for P-Vector on the coded input)."""
    out = []
    for n in nodes:
        for f in n.facts:
            if n.node_id == "allergies":
                out.append(f"Allergy: {f.get('substance')} ({f.get('kind')})")
            elif n.node_id == "problems.active":
                out.append(f"Active problem: {f.get('display')}")
            elif n.node_id == "meds.active":
                out.append(f"Current medication: {f.get('display')}")
            elif n.node_id == "vitals.latest":
                out.append(f"Vital sign: {f.get('display')} {f.get('value')} {f.get('unit') or ''} ({f.get('date')})")
            elif n.node_id.startswith("results."):
                out.append(f"Lab panel {f.get('date')}: {f.get('display')}")
            elif n.node_id.startswith("encounters."):
                out.append(f"Visit {f.get('date')}: {f.get('display')}")
    return out


def narrative_lines(nodes: list[PatientNode]) -> list[str]:
    return [f"{n.title}: {f['start'] or '?'} -> {f['stop'] or 'no end date'}: {f['description']}"
            + (f" ({f['value']})" if f.get("value") else "") for n in nodes for f in n.facts]


def chunks(lines: list[str], size: int = CHUNK_LINES) -> list[str]:
    return ["\n".join(lines[i:i + size]) for i in range(0, len(lines), size)]


def _embed(client: httpx.Client, texts: list[str]) -> np.ndarray:
    r = client.post(f"{config.OLLAMA_URL}/api/embed", json={"model": config.EMBED_MODEL, "input": texts}, timeout=600)
    r.raise_for_status()
    v = np.asarray(r.json()["embeddings"], dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def top_chunks(client: httpx.Client, parts: list[str], query: str, k: int = TOP_K, embed=None) -> list[int]:
    """Indices of the k chunks most similar to the query (nomic-embed-text, search_document / search_query)."""
    if not parts:
        return []
    embed = embed or (lambda texts: _embed(client, texts))
    docs = embed([f"search_document: {p}" for p in parts])
    q = embed([f"search_query: {query}"])[0]
    order = np.argsort(-(docs @ q), kind="stable")
    return [int(i) for i in order[:k]]


def dumps(items: dict) -> str:
    return json.dumps(items, ensure_ascii=False, sort_keys=True)


# ---- what the orchestrator calls ------------------------------------------------------------------------------

def profile_from_text(client: httpx.Client, text: str, weight: dict | None, rs: RuleSet, today: str, patient_id: str,
                      mode: str, evidence_ids: dict[str, str] | None = None
                      ) -> tuple[PatientProfile, dict[str, list[str]], int]:
    """extract() then profile_from_items(): the profile, the model's lists, the calls made."""
    items, calls = extract(client, text, today)
    return profile_from_items(items, weight, rs, today, patient_id, mode, evidence_ids), items, calls


def node_lines(nodes: list[PatientNode], narrative: bool) -> list[tuple[str, str]]:
    """(node id, line) for every fact of every non-root node, in tree order: what P-Vector cuts into chunks."""
    out = []
    for n in nodes:
        if n.kind == "root":
            continue
        lines = narrative_lines([n]) if narrative else coded_lines([n])
        out += [(n.node_id, line) for line in lines]
    return out


def chunk_table(lines: list[tuple[str, str]], size: int = CHUNK_LINES) -> list[tuple[str, list[str]]]:
    """Chunks of `size` lines: (text, the node ids its lines come from)."""
    out = []
    for i in range(0, len(lines), size):
        part = lines[i:i + size]
        out.append(("\n".join(t for _, t in part), list(dict.fromkeys(nid for nid, _ in part))))
    return out


_WEIGHT = re.compile(r"(\d{4}-\d{2}-\d{2}).*?Body Weight.*?([\d.]+)\s*(kg|\[lb_av\]|lb)?|"
                     r"Body Weight\s+([\d.]+)\s*(kg|\[lb_av\]|lb)?\s*\((\d{4}-\d{2}-\d{2})\)")


def weight_from_text(text: str) -> dict | None:
    """The newest Body Weight a text shows (a narrative row or a coded line); None when it shows none."""
    found = []
    for line in text.splitlines():
        m = _WEIGHT.search(line)
        if m and m.group(1):
            found.append((m.group(1), m.group(2), m.group(3)))
        elif m:
            found.append((m.group(6), m.group(4), m.group(5)))
    if not found:
        return None
    d, v, u = max(found)
    return {"loinc": "29463-7", "display": "Body Weight", "value": v, "unit": u or "kg", "date": d, "entry_id": ""}
