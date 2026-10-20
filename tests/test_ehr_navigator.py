"""Tree navigation and the dense baseline, with a scripted LLM and a fake embedder (no Ollama)."""

import json
import re
from uuid import UUID

import httpx
import numpy as np
import pytest

from api import ehr_document, ehr_navigator as nav
from api.llm import LLMError

P = {n: UUID(int=n) for n in range(1, 8)}


class ScriptedLLM:
    """Answers like a competent model: picks the section it is told to, lists what that text says is active."""

    def __init__(self, pick=("active_conditions",), extra_conditions=()):
        self.pick, self.extra, self.calls = list(pick), list(extra_conditions), []

    def __call__(self, messages):
        prompt = messages[-1]["content"]
        self.calls.append(prompt)
        if "table of contents" in prompt:
            return json.dumps({"sections": self.pick})
        text = prompt.split("Record text:")[1].split("List every medical condition")[0]
        active, section = [], ""
        for line in text.splitlines():
            if line.startswith("#"):
                section = line
            m = re.match(r"- (.*) \[SNOMED (\d+)\], since ", line)
            if m and "Active" in section:
                active.append({"code": m.group(2), "description": m.group(1)})
        return json.dumps({"conditions": active + self.extra})


def doc(ehr, n):
    return ehr_document.render_patient(ehr, P[n])


def test_tree_reads_only_the_chosen_section_and_finds_the_active_conditions(ehr):
    llm = ScriptedLLM()
    out = nav.tree_active_conditions(doc(ehr, 1), llm)
    assert out.error is None and out.codes == {"59621000", "160903007"} and out.selected == ["active_conditions"]
    assert out.llm_calls == 2 and out.rejected == []
    assert "Resolved conditions" not in llm.calls[1] and out.chars_read < len(doc(ehr, 1))
    assert "Essential hypertension" not in llm.calls[0]  # the table of contents carries no content


def test_a_stopped_condition_is_not_reported_when_the_right_section_is_read(ehr):
    out = nav.tree_active_conditions(doc(ehr, 3), ScriptedLLM())
    assert out.codes == {"314529007"}


def test_choosing_the_wrong_section_loses_the_answer_rather_than_inventing_one(ehr):
    out = nav.tree_active_conditions(doc(ehr, 1), ScriptedLLM(pick=["demographics"]))
    assert out.codes == set() and out.selected == ["demographics"]


def test_unknown_section_ids_are_ignored_and_no_valid_one_is_an_error(ehr):
    ok = nav.tree_active_conditions(doc(ehr, 1), ScriptedLLM(pick=["nope", "active_conditions", "active_conditions"]))
    assert ok.selected == ["active_conditions"]
    bad = nav.tree_active_conditions(doc(ehr, 1), ScriptedLLM(pick=["nope"]))
    assert bad.error and bad.llm_calls == 1 and bad.conditions == []


def test_ids_copied_with_brackets_or_quotes_still_match():
    assert nav.parse_sections('{"sections": ["[a]", " b ", "`c`", "[d]"]}', ["a", "b", "c"], 5) == ["a", "b", "c"]


def test_at_most_max_sections_are_read(ehr):
    llm = ScriptedLLM(pick=["demographics", "active_conditions", "allergies", "laboratory"])
    assert len(nav.tree_active_conditions(doc(ehr, 1), llm, max_sections=2).selected) == 2


def test_a_code_the_model_invented_is_dropped_and_reported(ehr):
    llm = ScriptedLLM(extra_conditions=[{"code": "99999", "description": "Made up"},
                                        {"code": "314529007", "description": "In the record but not shown"}])
    out = nav.tree_active_conditions(doc(ehr, 1), llm)
    assert "99999" in out.rejected and "99999" not in out.codes
    assert "314529007" in out.rejected  # a real code, but not in the sections it was shown


@pytest.mark.parametrize("reply", ["not json", "[1, 2]", '{"conditions": "x"}', '{"conditions": null}'])
def test_unusable_replies_become_an_error_not_an_exception(ehr, reply):
    def llm(messages):
        return json.dumps({"sections": ["active_conditions"]}) if "table of contents" in messages[-1]["content"] else reply
    out = nav.tree_active_conditions(doc(ehr, 1), llm)
    assert out.error and out.conditions == []


def test_json_wrapped_in_prose_is_accepted():
    assert nav.parse_json('Sure! {"sections": ["a"]} Hope that helps.') == {"sections": ["a"]}


def test_an_llm_failure_is_reported(ehr):
    def down(messages):
        raise LLMError("Ollama is not reachable")
    out = nav.tree_active_conditions(doc(ehr, 1), down)
    assert out.error == "Ollama is not reachable" and out.llm_calls == 0


def test_codes_match_whole_numbers_only():
    assert nav.appears_in("5962", "x [SNOMED 59621000]") is False
    assert nav.appears_in("59621000", "x [SNOMED 59621000], since") is True


# --- dense baseline -------------------------------------------------------------------------


def keyword_embedder(words):
    """One dimension per word: a piece is close to the question when it contains the words."""
    def docs(texts):
        v = np.array([[t.lower().count(w) for w in words] for t in texts], dtype=np.float32) + 1e-3
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def query(text):
        v = np.array([1.0 if w in ("active", "since") else 0.0 for w in words], dtype=np.float32) + 1e-3
        return v / np.linalg.norm(v)
    return docs, query


def test_chunks_are_fixed_size_on_line_boundaries_and_cover_the_document(ehr):
    d = doc(ehr, 7)
    pieces = nav.chunk_document(d, 200)
    assert "".join(pieces) == d and len(pieces) > 1
    assert all(p.endswith("\n") for p in pieces)


def test_dense_reads_the_k_closest_pieces_in_document_order_and_checks_codes(ehr):
    docs, query = keyword_embedder(["active", "since", "stopped", "to"])
    llm = ScriptedLLM()
    out = nav.dense_active_conditions(doc(ehr, 7), llm, docs, query, k=2, max_chars=150)
    assert out.method == "dense" and len(out.selected) == 2 and out.selected == sorted(out.selected, key=int)
    assert out.llm_calls == 1 and out.chars_read > 0 and out.error is None
    assert out.codes <= {"714628002", "55822004", "433144002"}  # nothing outside the record


def test_dense_reports_an_embedding_failure(ehr):
    def boom(texts):
        raise httpx.ConnectError("refused")
    out = nav.dense_active_conditions(doc(ehr, 1), ScriptedLLM(), boom, lambda q: np.ones(2))
    assert out.error and "embedding" in out.error and out.llm_calls == 0
