"""M5 V6: the gold review tool is blind and its rows apply at the freeze (no DB, no model)."""

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import freeze_testset as fz
import testset_review as tr

FORBIDDEN = {"api", "tag", "lexicon", "ingest", "checker", "make_testset"}


def test_the_review_tool_imports_no_pipeline_tagger_or_checker():
    tree = ast.parse(Path(tr.__file__).read_text(encoding="utf-8"))
    imported = {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not imported & FORBIDDEN, imported & FORBIDDEN


@pytest.fixture
def tool(tmp_path, monkeypatch):
    cand = tmp_path / "candidates"
    cand.mkdir()
    gold = {"intent": "search", "constraints": {"allergens_exclude": ["milk"], "ingredients_exclude": [], "diet": None,
                                                "max_total_minutes": None}}
    (cand / "t2.jsonl").write_text(json.dumps({"id": "t2_001", "set": "t2", "lang": "en", "text": "a milk-free soup",
                                               "gold": gold, "v2": {"recipe_id": 7}}) + "\n"
                                   + json.dumps({"id": "t2_002", "set": "t2", "lang": "vi", "text": "minh di ung tom",
                                                 "gold": None, "needs_gold": True, "source": "handwritten"}) + "\n",
                                   encoding="utf-8")
    monkeypatch.setattr(tr, "CAND", cand)
    monkeypatch.setattr(tr, "REVIEW", tmp_path / "review.csv")
    return TestClient(tr.create_app())


def test_an_item_shows_text_and_proposed_gold_only(tool):
    item = tool.get("/api/item/1").json()
    assert set(item) == tr.ITEM_FIELDS and "v2" not in item and item["gold"]["constraints"]["allergens_exclude"] == ["milk"]


def test_ok_needs_a_gold_edit_needs_a_valid_one_and_the_last_row_wins(tool):
    assert tool.post("/api/review/2", json={"decision": "ok"}).status_code == 422  # handwritten: nothing to accept
    bad = {"intent": "dance", "constraints": {}}
    assert tool.post("/api/review/2", json={"decision": "edit", "gold": bad}).status_code == 422
    good = {"intent": "search", "constraints": {"allergens_exclude": ["crustacean_shellfish"], "ingredients_exclude": [],
                                                "diet": None, "max_total_minutes": None}}
    tool.post("/api/review/1", json={"decision": "drop", "note": "lặp"})
    tool.post("/api/review/1", json={"decision": "ok"})
    assert tool.post("/api/review/2", json={"decision": "edit", "gold": good}).json()["reviewed"] == 2
    sets, counts = fz.apply(tr.items(), tr.saved())
    assert [it["id"] for it in sets["t2"]] == ["t2_001", "t2_002"] and counts["t2"] == {"ok": 1, "edit": 1, "drop": 0}
    assert sets["t2"][1]["gold"]["constraints"]["allergens_exclude"] == ["crustacean_shellfish"]
    assert "needs_gold" not in sets["t2"][1]


def test_the_freeze_refuses_unreviewed_items(tool):
    with pytest.raises(ValueError, match="2 items not reviewed"):
        fz.apply(tr.items(), tr.saved())


def test_a_frozen_test_set_has_not_changed():
    frozen = fz.OUT / "frozen.json"
    if not frozen.exists():
        pytest.skip("the A3 test set is not frozen yet")
    assert json.loads(frozen.read_text(encoding="utf-8"))["sha256"] == fz.digests()
