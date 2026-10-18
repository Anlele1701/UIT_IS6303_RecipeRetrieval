"""MV4c: no prompt may be cut by Ollama (it keeps half of num_ctx and drops the START: the system prompt)."""

import json

import httpx
import pytest

from api.patient import baselines
from api.pipeline import llm, m6_generate as m6, m7_verify as m7


def fake_client(prompt_tokens: int, content: str = '{"a": 1}') -> httpx.Client:
    def handler(request):
        return httpx.Response(200, json={"message": {"content": content}, "prompt_eval_count": prompt_tokens})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_prompt_surely_too_long_is_refused_before_the_call():
    with pytest.raises(llm.PromptTooLong):
        llm.check_fits([{"role": "user", "content": "x" * 40000}], 16384)
    llm.check_fits([{"role": "user", "content": "x" * 20000}], 16384)  # 5,000 tokens at most: may fit


def test_a_cut_prompt_raises_and_is_not_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE", tmp_path / "llm.jsonl")
    monkeypatch.setattr(llm, "_cache", {})
    msgs = [{"role": "user", "content": "hello"}]
    with pytest.raises(llm.PromptTooLong):  # Ollama read num_ctx/2 tokens: it cut the prompt
        llm.chat_json(fake_client(4098), {"type": "object"}, msgs, num_ctx=8192)
    assert not (tmp_path / "llm.jsonl").exists()
    assert llm.chat_json(fake_client(900), {"type": "object"}, msgs, num_ctx=8192) == {"a": 1}
    assert not issubclass(llm.PromptTooLong, llm.LLMError)  # callers that retry on LLMError must not swallow it


def test_fit_views_keeps_undated_facts_then_the_newest():
    views = [{"node_id": "allergies", "title": "A", "facts": [{"substance": "Peanut"}]},
             {"node_id": "results.2020", "title": "R", "facts": [{"date": f"2020-{m:02d}-01", "display": "x" * 300}
                                                               for m in range(1, 13)]}]
    out, omitted = m6.fit_views(views, budget=2000)
    kept = [f["date"] for f in out[1]["facts"]]
    assert out[0]["facts"] == [{"substance": "Peanut"}]
    assert kept and kept == sorted(kept) and kept[-1] == "2020-12-01"  # the newest, in the node's own order
    assert omitted == {"results.2020": 12 - len(kept)} and out[1]["older_entries_not_shown"] == omitted["results.2020"]
    assert len(json.dumps(out, ensure_ascii=False)) <= 2000
    assert m6.fit_views(views[:1]) == (views[:1], {})  # small enough: untouched


def test_values_answer_reads_narrative_rows():
    v = [{"node_id": "narrative.problems", "facts": [{"description": "Essential hypertension (disorder)",
                                                       "date": "1993-03-05", "stop": None}]}]
    assert "Essential hypertension (disorder) (1993-03-05) [H:narrative.problems]" in m7.values_answer(v, "en")


def test_a_long_text_is_read_in_pieces_that_keep_their_section_title():
    text = "## Medications\n" + "\n".join(f"2020-01-01 -> no end date: drug {i}" for i in range(400)) + \
        "\n## Problems\n2001-01-01 -> no end date: Essential hypertension (disorder)"
    parts = baselines.pieces(text, limit=2000)
    assert len(parts) > 1 and all(len(p) <= 2000 for p in parts)
    assert all(p.startswith("## ") for p in parts)
    lines = [ln for p in parts for ln in p.splitlines() if not ln.startswith("## ")]
    assert lines == [ln for ln in text.splitlines() if not ln.startswith("## ")]  # nothing lost, nothing doubled


def test_extract_merges_the_pieces(monkeypatch):
    monkeypatch.setattr(baselines, "PIECE_CHARS", 60)
    replies = iter([{"food_allergies": ["Peanut"], "conditions": [], "medications": ["A"]},
                    {"food_allergies": ["peanut "], "conditions": ["B"], "medications": []}])
    monkeypatch.setattr(baselines, "chat_json", lambda *a, **k: next(replies))
    monkeypatch.setattr(baselines, "pieces", lambda text, limit=0: ["one", "two"])
    items, calls = baselines.extract(None, "one two", "2026-10-23")
    assert calls == 2 and items == {"food_allergies": ["Peanut"], "conditions": ["B"], "medications": ["A"]}


def test_generation_is_capped_and_a_cut_answer_is_reported():
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content)["options"])
        lines = [{"message": {"content": "loop "}, "done": False},
                 {"message": {"content": ""}, "done": True, "done_reason": "length", "prompt_eval_count": 100,
                  "eval_count": llm.GEN_MAX_TOKENS}]
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines).encode())
    usage = {}
    out = "".join(llm.chat_stream(httpx.Client(transport=httpx.MockTransport(handler)),
                                  [{"role": "user", "content": "hi"}], usage=usage))
    assert out == "loop " and sent["num_predict"] == llm.GEN_MAX_TOKENS and usage["done_reason"] == "length"
