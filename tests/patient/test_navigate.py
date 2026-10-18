"""V2 node selection (spec 8, test_navigate): bounded, made-up ids dropped, fallback to fixed nodes. No Ollama."""

from pathlib import Path

import pytest

from api.patient import ccda, navigate, rules
from api.patient.summarize import summarize
from api.patient.tree import build_tree
from api.pipeline.llm import LLMError

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
FIXED = ["allergies", "problems.active", "meds.active", "vitals.latest"]


@pytest.fixture(scope="module")
def rs():
    return rules.load_rules()


@pytest.fixture(scope="module")
def nodes(rs):
    return summarize(build_tree(ccda.read_record(FIXTURE, "sample", rs.p7)[0]), rs)


def fake(monkeypatch, replies):
    calls = []

    def chat_json(client, schema, messages, **kw):
        calls.append(messages)
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(navigate, "chat_json", chat_json)
    return calls


def test_no_context_needed_means_no_model_call(nodes, rs, monkeypatch):
    calls = fake(monkeypatch, [])
    sel = navigate.select_nodes(nodes, "món tối nhanh", False, "vectorless", rs, None)
    assert sel.node_ids == FIXED and sel.llm_calls == 0 and not calls


def test_one_call_keeps_real_ids_and_drops_made_up_ones(nodes, rs, monkeypatch):
    calls = fake(monkeypatch, [{"node_ids": ["results.2021", "results.1999", "encounters.2025", "encounters.2024",
                                             "encounters.2023"]}])
    sel = navigate.select_nodes(nodes, "lần xét nghiệm gần nhất?", True, "vectorless", rs, None)
    assert sel.node_ids == FIXED + ["results.2021", "encounters.2025", "encounters.2024"]  # at most 3, in order
    assert sel.dropped == ["results.1999"] and sel.llm_calls == 1 and len(calls) == 1


def test_two_failures_fall_back_to_the_fixed_nodes(nodes, rs, monkeypatch):
    fake(monkeypatch, [LLMError("bad"), LLMError("bad")])
    sel = navigate.select_nodes(nodes, "lab results?", True, "vectorless", rs, None)
    assert sel.node_ids == FIXED and sel.fallback and sel.llm_calls == 2


def test_direct_never_calls_a_model(nodes, rs, monkeypatch):
    calls = fake(monkeypatch, [])
    assert navigate.select_nodes(nodes, "lab results?", True, "direct", rs, None).node_ids == FIXED and not calls


def test_the_prompt_is_only_the_table_of_contents(nodes, rs, monkeypatch):
    calls = fake(monkeypatch, [{"node_ids": []}])
    navigate.select_nodes(nodes, "visits?", True, "vectorless", rs, None)
    text = calls[0][1]["content"]
    assert "results.2021" in text and "facts" not in text and "entry_id" not in text
    for word in ["Barton704", "Upton904", "Allergic disorder", "Well child"]:
        assert word not in text


def test_nofixed_reads_only_what_the_model_picks_even_the_fixed_nodes(nodes, rs, monkeypatch):
    calls = fake(monkeypatch, [{"node_ids": ["meds.active", "results.2021", "allergies"]}])
    sel = navigate.select_nodes(nodes, "món tối", False, "vectorless_nofixed", rs, None)  # needs_context is moot
    assert sel.node_ids == ["meds.active", "results.2021", "allergies"] and sel.llm_calls == 1
    assert "at most 6" in calls[0][0]["content"] and "allergies" in calls[0][1]["content"]


def test_vector_mode_does_not_walk_the_tree(nodes, rs):
    with pytest.raises(ValueError, match="chunks"):
        navigate.select_nodes(nodes, "x", True, "vector", rs, None)


def test_the_patient_golden_draft_is_well_formed_and_still_a_draft():
    import json
    root = Path(__file__).resolve().parents[2]
    rows = [json.loads(line) for line in
            (root / "tests" / "golden" / "m1_patient_cases_draft.jsonl").read_text(encoding="utf-8").splitlines()]
    keys = {"id", "status", "message", "intent", "needs_record_context", "allergens", "excl", "remove", "diet", "minutes"}
    assert len({r["id"] for r in rows}) == len(rows) == 14
    for r in rows:
        assert keys <= set(r) and isinstance(r["remove"], list), r["id"]
        assert r["status"].startswith("draft"), r["id"]  # only Thy turns a case into approved


def test_only_the_nofixed_prompt_says_unpicked_sections_are_not_read():
    rs = rules.load_rules()
    assert navigate.NOFIXED_NOTE in navigate.prompt("q", [], rs, 6, nofixed=True)[0]["content"]
    assert navigate.NOFIXED_NOTE not in navigate.prompt("q", [], rs)[0]["content"]  # P-Vectorless cache keys kept


def test_the_prompt_carries_the_record_date_not_the_clock():
    rs = rules.load_rules()
    assert "dated 2026-10-23" in navigate.prompt("q", [], rs, today="2026-10-23")[0]["content"]
    assert "dated" not in navigate.prompt("q", [], rs)[0]["content"]
