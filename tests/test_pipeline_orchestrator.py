"""The orchestrator on the test DB with fake models: events, stored state, trace rows, M7 regeneration.
The same turns with the real models are the demo scenarios in test_pipeline_demo.py (slow)."""

import numpy as np
import pytest

import ingest
import tag
from api.pipeline import orchestrator as orch
from api.pipeline.flags import preset
from api.pipeline.lexicon import RuntimeLexicon
from api.pipeline.schemas import Constraints, Removal, Understanding

QVEC = "[" + ",".join(["0.036"] * 768) + "]"


@pytest.fixture
def bot(recipes, fake_embed, monkeypatch):
    report, tables = tag.tag_all(recipes)
    tag.write_tables(recipes, tables)
    ingest.run(recipes, ["chunk", "sentence"])
    monkeypatch.setattr(orch, "embed_query", lambda client, text: QVEC)
    return orch.Assistant(recipes, client=None, scorer=lambda q, texts: np.zeros(len(texts)), lex=RuntimeLexicon(),
                          strategy="sentence")


def fake_models(monkeypatch, understood: list[Understanding], answers: list[str]):
    monkeypatch.setattr(orch, "understand", lambda client, lex, message, history, current: understood.pop(0))
    monkeypatch.setattr(orch.m6, "generate", lambda client, messages, usage=None: iter([answers.pop(0)]))


def turn(bot, sid, msg, name="S"):
    return {e.type: e.data for e in bot.run_turn(sid, msg, preset(name))}


def test_a_filtered_turn_streams_events_stores_state_and_traces_every_stage(bot, monkeypatch):
    shrimp_free = Understanding(lang="vi", query_en="garlic shrimp toast",
                                constraints=Constraints(allergens_exclude=["crustacean_shellfish"]))
    fake_models(monkeypatch, [shrimp_free], ["Thử [R1] hoặc [R2].", "Thử [R2]."])
    sid = bot.new_session()
    ev = turn(bot, sid, "món tỏi không tôm")
    assert ev["constraints"]["constraints"]["allergens_exclude"] == ["crustacean_shellfish"]
    assert 1 not in [r["id"] for r in ev["recipes"]]
    # M7: R1 is outside the context, so the answer is regenerated once
    assert ev["done"]["removed"] == [1] and ev["done"]["regenerated"]
    stages = [s for (s,) in bot.conn.execute("SELECT stage FROM retrieval_trace WHERE message_id = %s ORDER BY id",
                                             [ev["done"]["message_id"]])]
    assert stages == ["m1", "m2", "m3", "m4", "m5", "m6", "m7"]
    assert [it.value for it in bot.state(sid).items] == ["crustacean_shellfish"]


def test_m7_regeneration_that_still_fails_has_its_bad_citations_stripped(bot, monkeypatch):
    u = Understanding(query_en="shrimp", constraints=Constraints(allergens_exclude=["crustacean_shellfish"]))
    fake_models(monkeypatch, [u], ["[R1]", "Still [R1]."])
    ev = turn(bot, bot.new_session(), "shrimp without shellfish")
    assert ev["done"]["answer"] == "Still." and not ev["done"]["verified"]


def test_s_verify_measures_but_keeps_the_answer(bot, monkeypatch):
    u = Understanding(query_en="shrimp", constraints=Constraints(allergens_exclude=["crustacean_shellfish"]))
    fake_models(monkeypatch, [u], ["[R1]"])
    ev = turn(bot, bot.new_session(), "shrimp without shellfish", "S-Verify")
    assert ev["done"]["answer"] == "[R1]" and not ev["done"]["verified"] and not ev["done"]["regenerated"]


def test_state_carries_over_and_a_removal_lifts_it(bot, monkeypatch):
    fake_models(monkeypatch, [Understanding(query_en="toast", constraints=Constraints(allergens_exclude=["peanut"])),
                              Understanding(intent="refine", query_en="toast", remove=Removal(allergens=["peanut"]))],
                ["[R2]", "[R2]"])
    sid = bot.new_session()
    turn(bot, sid, "toast, no peanuts")
    assert [it.value for it in bot.state(sid).items] == ["peanut"]
    turn(bot, sid, "I can eat peanuts now")
    assert bot.state(sid).items == [] and len(bot.history(sid)) == 4


def test_b0_has_no_understanding_no_answer_and_ranks_like_a1(bot, monkeypatch):
    fake_models(monkeypatch, [], [])
    ev = turn(bot, bot.new_session("B0"), "garlic shrimp", "B0")
    assert ev["recipes"][0]["id"] == 1 and "token" not in ev and ev["done"]["answer"] == ""


def test_clarify_asks_back_without_retrieval(bot, monkeypatch):
    fake_models(monkeypatch, [Understanding(lang="vi", clarify="Bạn muốn nói hành lá hay hành tây?")], [])
    ev = turn(bot, bot.new_session(), "không hành")
    assert ev["token"].startswith("Bạn muốn") and "recipes" not in ev
