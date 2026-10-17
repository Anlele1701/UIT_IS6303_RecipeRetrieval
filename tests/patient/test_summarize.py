"""MV1: V1c summaries. The LLM path runs against a fake chat_json; no Ollama."""

from pathlib import Path

import pytest

from api.patient import ccda, rules, summarize
from api.patient.tree import build_tree
from api.pipeline.llm import LLMError

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"


@pytest.fixture(scope="module")
def nodes():
    return build_tree(ccda.read_record(FIXTURE, "sample", rules.load_p7())[0])


def test_template_fills_context_nodes_only(nodes):
    out = summarize.summarize(nodes, "template")
    for n in out:
        if n.kind == "context":
            assert n.summary and n.summary_source == "template"
        else:
            assert n.summary is None and n.summary_source is None
    cbc = next(n for n in out if n.node_id == "results.2021")
    assert cbc.summary == "1 lab panel: CBC panel."


def test_template_counts_encounter_kinds(nodes):
    y = next(n for n in summarize.summarize(nodes) if n.node_id == "encounters.2025")
    assert y.summary == "2 encounters: Encounter for check up, Encounter for symptom."


def test_llm_summary_used_when_the_model_answers(nodes, monkeypatch):
    calls = []

    def fake(client, schema, messages, **kw):
        calls.append(messages)
        return {"summary": "One CBC panel in 2021."}
    monkeypatch.setattr(summarize, "chat_json", fake)
    out = summarize.summarize(nodes, "llm", client=object())
    cbc = next(n for n in out if n.node_id == "results.2021")
    assert (cbc.summary, cbc.summary_source) == ("One CBC panel in 2021.", "llm")
    assert len(calls) == sum(n.kind == "context" for n in nodes)  # fixed and root nodes never go to the model


def test_llm_failing_twice_falls_back_to_the_template(nodes, monkeypatch):
    attempts = []

    def broken(client, schema, messages, **kw):
        attempts.append(1)
        raise LLMError("not JSON")
    monkeypatch.setattr(summarize, "chat_json", broken)
    node = next(n for n in nodes if n.node_id == "results.2021")
    out = summarize.summarize([node], "llm", client=object())[0]
    assert (out.summary, out.summary_source) == ("1 lab panel: CBC panel.", "template")
    assert len(attempts) == 2


def test_prompt_holds_no_identity(nodes):
    text = "".join(m["content"] for n in nodes if n.kind == "context" for m in summarize.prompt(n))
    for word in ["Barton704", "Upton904", "raceCode"]:
        assert word not in text
