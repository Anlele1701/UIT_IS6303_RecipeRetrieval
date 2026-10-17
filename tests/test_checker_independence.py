"""The independent checker shares nothing with the tagger (CLAUDE.md rule 7)."""

import ast
from pathlib import Path

import checker

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "scripts" / "checker.py").read_text(encoding="utf-8")
FORBIDDEN_MODULES = {"lexicon", "tag", "ingest", "api"}
FORBIDDEN_TEXT = ["recipe_tag", "ingredient_allergen", "recipe_ingredient_norm", "data/lexicon", "allergens_may",
                  "rules.csv", "allergen_map", "ingredients.csv", "chunk"]


def test_no_tagger_module_is_imported():
    tree = ast.parse(SOURCE)
    imported = {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not imported & FORBIDDEN_MODULES, imported & FORBIDDEN_MODULES


def test_no_tag_table_or_lexicon_file_is_named():
    for word in FORBIDDEN_TEXT:
        assert word not in SOURCE, word


def test_the_checker_model_is_not_the_generator_family():
    assert not checker.CHECKER_MODEL.startswith("qwen")


LINES = ["1 cup butter", "2 eggs", "salt to taste"]


def test_parse_maps_answers_by_number_and_checks_the_evidence():
    out = checker.parse([{"i": 1, "contains": "yes", "evidence_line": "1 cup butter"},
                         {"i": 2, "contains": "yes", "evidence_line": "two eggs"},  # not a real line
                         {"i": 3, "contains": "no", "evidence_line": ""}],
                        ["allergen:milk", "allergen:egg", "allergen:fish"], LINES)
    assert out["allergen:milk"] == checker.Verdict("yes", "1 cup butter", True)
    assert out["allergen:egg"].evidence_ok is False
    assert out["allergen:fish"] == checker.Verdict("no", "", True)


def test_a_missing_or_invalid_answer_is_an_error_never_no():
    out = checker.parse([{"i": 1, "contains": "maybe", "evidence_line": ""}], ["allergen:milk", "allergen:egg"], LINES)
    assert out["allergen:milk"].contains == "error" and out["allergen:egg"].contains == "error"


def test_evidence_matches_despite_double_spaces():
    out = checker.parse([{"i": 1, "contains": "yes", "evidence_line": "2 eggs"}], ["allergen:egg"], ["2  eggs"])
    assert out["allergen:egg"].evidence_ok


def test_questions_are_asked_in_batches(recipes, monkeypatch, tmp_path):
    monkeypatch.setattr(checker, "CACHE", tmp_path / "cache.jsonl")
    sizes = []

    def fake_ask(client, title, lines, constraints):
        sizes.append(len(constraints))
        return [{"i": k, "contains": "no", "evidence_line": ""} for k in range(1, len(constraints) + 1)]

    monkeypatch.setattr(checker, "ask", fake_ask)
    checker.check(recipes, None, 1, checker.M2_CONSTRAINTS, {})
    assert sizes == [6, 5]


def test_check_asks_only_for_uncached_constraints(recipes, monkeypatch, tmp_path):
    monkeypatch.setattr(checker, "CACHE", tmp_path / "cache.jsonl")
    asked = []

    def fake_ask(client, title, lines, constraints):
        asked.append(list(constraints))
        return [{"i": k, "contains": "no", "evidence_line": ""} for k in range(1, len(constraints) + 1)]

    monkeypatch.setattr(checker, "ask", fake_ask)
    cache = {}
    checker.check(recipes, None, 1, ["allergen:milk", "allergen:egg"], cache)
    out = checker.check(recipes, None, 1, ["allergen:milk", "allergen:fish"], cache)
    assert asked == [["allergen:milk", "allergen:egg"], ["allergen:fish"]]
    assert out["allergen:milk"].contains == "no"
    assert len(checker.load_cache(tmp_path / "cache.jsonl")) == 3


def test_an_incomplete_reply_is_asked_once_more(recipes, monkeypatch, tmp_path):
    monkeypatch.setattr(checker, "CACHE", tmp_path / "cache.jsonl")
    replies = [[], [], [{"i": 1, "contains": "yes", "evidence_line": "1 lb shrimp"}]]
    monkeypatch.setattr(checker, "ask", lambda *a: replies.pop(0))
    out = checker.check(recipes, None, 1, ["allergen:crustacean_shellfish"], {})
    assert out["allergen:crustacean_shellfish"] == checker.Verdict("yes", "1 lb shrimp", True) and not replies


# ---- the adjudication step shares nothing with the tagger either (Thy, after MV3) ----------------------------

ADJ_SOURCE = (ROOT / "scripts" / "adjudicate.py").read_text(encoding="utf-8")


def test_adjudication_imports_no_tagger_module_and_names_no_tag_table():
    tree = ast.parse(ADJ_SOURCE)
    imported = {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not imported & (FORBIDDEN_MODULES - {"api"}), imported  # api.config only, for DATABASE_URL
    assert "pipeline" not in ADJ_SOURCE and "patient" not in ADJ_SOURCE.split('"""', 2)[2]
    for word in FORBIDDEN_TEXT:
        assert word not in ADJ_SOURCE, word
