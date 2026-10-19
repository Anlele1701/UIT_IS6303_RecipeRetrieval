"""M6: eval_a3 metrics, sampling and the human check (no DB, no model)."""

import ast
from pathlib import Path

import pytest

import eval_a3 as ea
import human_check as hc


def test_ndcg_recall_mrr_against_the_pool():
    rel = {1: 2, 2: 0, 3: 1, 4: 2}
    assert ea.ndcg([1, 4, 3], rel) == pytest.approx(1.0)
    assert ea.ndcg([2, 3, 1], rel) < ea.ndcg([1, 3, 2], rel)
    assert ea.recall([1, 2], rel) == pytest.approx(1 / 3) and ea.mrr([2, 3], rel) == 0.5
    assert ea.ndcg([1], {1: 0}) is None and ea.mrr([1], {}) is None  # nothing relevant in the pool


def test_slot_f1_counts_type_and_canonical_value():
    pred = {"allergens_exclude": ["peanut"], "ingredients_exclude": ["onion"], "diet": None, "max_total_minutes": 30}
    gold = {"allergens_exclude": ["peanut"], "ingredients_exclude": [], "diet": "vegan", "max_total_minutes": 30}
    assert ea.slot_counts(pred, gold) == (2, 1, 1)
    assert not ea.has_constraint({"allergens_exclude": [], "ingredients_exclude": [], "diet": None})


def test_citation_validity_and_safety():
    s = ea.citation_scores("Try [R1] and [R9], or [R1] again", context=[1, 2, 3], ok={2, 3})
    assert s == {"cited": 2, "citation_validity": 0.5, "citation_safety": 0.0}
    assert ea.citation_scores("no recipe", [1], {1})["citation_validity"] is None


def test_the_sample_is_seeded_and_balanced():
    items = [{"id": f"t2_{i:03d}", "lang": "vi" if i % 3 else "en"} for i in range(40)]
    a, b = ea.balanced_sample(items, 10), ea.balanced_sample(list(reversed(items)), 10)
    assert a == b and sum(it["lang"] == "en" for it in a) == 5
    assert sum(ea.SAMPLE.values()) == 37  # Thy: ~10% of each set


def test_turn_counts_add_up_to_about_370():
    t4_turns = 3  # the T4 scripts have 2-4 turns
    n = (ea.SAMPLE["t1"] + ea.SAMPLE["t2"] + ea.SAMPLE["t3"]) * len(ea.MAIN) \
        + ea.SAMPLE["t4"] * t4_turns * (len(ea.MAIN) + len(ea.T4_ONLY))
    assert 340 <= n <= 400


def test_errors_tag_s_turns_only_and_find_lost_state():
    g = {"allergens_exclude": ["egg"], "ingredients_exclude": [], "diet": None, "max_total_minutes": 30}
    t = {"preset": "S", "set": "t4", "turn": 2, "route": "retrieve", "recipe_ids": [1], "ranked": [1],
         "constraints": {"allergens_exclude": [], "ingredients_exclude": [], "diet": None, "max_total_minutes": 30}}
    groups = ea.error_groups(t, {"slot_fn": 1}, g, {"intent": "refine"}, {}, [], {}, {}, lambda r: [])
    assert "F9_lost_state" in groups and "F1_constraint_extraction" in groups
    assert ea.error_groups({**t, "preset": "B0"}, {"slot_fn": 1}, g, {}, {}, [], {}, {}, lambda r: []) == []


def test_kappa():
    assert hc.kappa([0, 1, 2, 2], [0, 1, 2, 2]) == 1.0
    assert hc.kappa([1, 1, 0, 0], [1, 0, 1, 0]) == 0.0


def test_the_human_check_page_hides_the_machine():
    tree = ast.parse(Path(hc.__file__).read_text(encoding="utf-8"))
    get_item = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "item")
    src = ast.unparse(get_item)
    assert "key" not in src and "judge" not in src  # the page serves the sample, never the key file
    html = Path(hc.PAGE).read_text(encoding="utf-8")
    assert "judge" not in html.split("<script>")[1] and "contains\"]" not in html


def test_the_scoring_hints_never_carry_the_machine_answer():
    tree = ast.parse(Path(hc.__file__).read_text(encoding="utf-8"))
    sample = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "make_sample")
    hints = [ast.unparse(v) for d in ast.walk(sample) if isinstance(d, ast.Dict)
             for k, v in zip(d.keys, d.values) if isinstance(k, ast.Constant) and k.value == "hint"]
    assert len(hints) == 3  # relevance, answer, checker
    for h in hints:  # built from the query, the frozen gold, the answer text and fixed group notes only
        assert not any(w in h for w in ("judge", "verdict", "contains", "key", "score", "rel["))
    assert "yes" not in " ".join(hc.GROUP_VI.values()) and hc.gold_text(None) == "không có ràng buộc"


def test_the_sheet_round_trips_and_stays_blind(tmp_path, monkeypatch):
    import csv
    import json
    sample = {"items": [
        {"task": "relevance", "id": "rel_01", "query": "q", "recipe": {"recipe_id": 1, "title": "T", "ingredients": ["a"]},
         "hint": ["h"]},
        {"task": "answer", "id": "ans_01", "query": "q", "answer": "A [R1]", "hint": [],
         "context": [{"recipe_id": 1, "title": "T", "ingredients": ["a"]}]},
        {"task": "checker", "id": "chk_01", "item": "milk", "constraint": "allergen:milk",
         "recipe": {"recipe_id": 2, "title": "U", "ingredients": ["butter"]}}]}
    (tmp_path / "s.json").write_text(json.dumps(sample), encoding="utf-8")
    monkeypatch.setattr(hc, "SAMPLE", tmp_path / "s.json")
    monkeypatch.setattr(hc, "OUT", tmp_path / "out.csv")
    monkeypatch.setattr(hc, "ROOT", tmp_path)
    sheet = tmp_path / "sheet.csv"
    hc.export_sheet(sheet)
    text = sheet.read_text(encoding="utf-8-sig")
    assert "judge" not in text and "allergen:milk" not in text  # display fields only
    rows = list(csv.DictReader(text.splitlines()))
    rows[0]["score"] = "2"
    rows[1].update(faithful="có", answers="1", wrong_citation="0")
    rows[2]["contains"] = "x"
    with open(sheet, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=hc.SHEET_FIELDS)
        w.writeheader()
        w.writerows(rows)
    assert hc.import_sheet(sheet).startswith("not imported") and not hc.OUT.exists()  # one bad row blocks all
    rows[2]["contains"] = "không chắc"
    with open(sheet, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=hc.SHEET_FIELDS)
        w.writeheader()
        w.writerows(rows)
    hc.import_sheet(sheet)
    lab = {i: json.loads(r["label"]) for i, r in hc.labels().items()}
    assert lab == {"rel_01": {"score": 2}, "ans_01": {"faithful": True, "answers": 1, "wrong_citation": False},
                   "chk_01": {"contains": "unsure"}}
    assert "kept 3" in hc.import_sheet(sheet)  # a second import does not overwrite


def test_a_broken_checker_reply_becomes_an_error_verdict_not_a_crash():
    import json
    from types import SimpleNamespace

    class Checker:
        Verdict = staticmethod(lambda contains, line, ok: SimpleNamespace(contains=contains))
        calls = 0

        def check(self, conn, client, rid, cons, cache):
            Checker.calls += 1
            raise json.JSONDecodeError("cut", "{", 1)
    out = ea.safe_check(Checker(), None, None, 7, ["allergen:milk"], {})
    assert Checker.calls == 2 and out["allergen:milk"].contains == "error"
