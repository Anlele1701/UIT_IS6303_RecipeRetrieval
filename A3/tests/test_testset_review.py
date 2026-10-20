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
    monkeypatch.setattr(tr, "DRAFT", tmp_path / "draft.csv")
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
    assert [it["id"] for it in sets["t2"]] == ["t2_001", "t2_002"] and counts["t2"] == {"ok": 1, "edit": 1, "drop": 0, "bulk_ok": 0}
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


def write_draft(path, rows):
    import csv
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item_id", "decision", "gold", "note", "flagged", "flag_reason", "reviewer",
                                          "drafted_at"], lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({"reviewer": "claude-draft", "drafted_at": "x", "note": "", "flag_reason": "", **r})


def test_draft_mode_shows_the_draft_and_ok_accepts_its_gold(tool):
    hand = {"intent": "search", "constraints": {"allergens_exclude": ["crustacean_shellfish"], "ingredients_exclude": [],
                                                "diet": None, "max_total_minutes": None}}
    write_draft(tr.DRAFT, [{"item_id": "t2_001", "decision": "ok", "gold": "", "flagged": False},
                           {"item_id": "t2_002", "decision": "edit", "gold": json.dumps(hand), "flagged": True,
                            "flag_reason": "viết tay"}])
    st = tool.get("/api/state").json()
    assert st["has_draft"] and st["flagged_open"] == 1 and st["unflagged_open"] == 1 and st["next_flagged"] == 2
    item = tool.get("/api/item/2").json()
    assert item["draft"]["gold"] == hand and item["draft"]["flagged"]
    assert tool.get("/api/next", params={"after": 0, "only_flagged": True}).json() == {"order": 2}
    tool.post("/api/review/2", json={"decision": "ok"})  # Thy accepts the draft gold
    assert tool.post("/api/bulk_accept", json={"confirm": False}).status_code == 422
    assert tool.post("/api/bulk_accept", json={"confirm": True}).json()["accepted"] == 1
    sets, counts = fz.apply(tr.items(), tr.saved())
    assert sets["t2"][1]["gold"] == hand and counts["t2"]["bulk_ok"] == 1
    assert all(r["reviewer"] == "Thy" for r in tr.saved().values())


def test_the_freeze_takes_only_thys_rows(tool):
    tool.post("/api/review/1", json={"decision": "ok"})
    reviews = tr.saved()
    reviews["t2_002"] = {"item_id": "t2_002", "decision": "ok", "gold": "", "note": "", "reviewer": "claude-draft"}
    with pytest.raises(ValueError, match="not Thy's"):
        fz.apply(tr.items(), reviews)
