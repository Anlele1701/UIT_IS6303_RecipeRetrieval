"""The labeling tool must stay blind (CLAUDE.md rule 6): no tags, lexicon or checker output reach it."""

import ast
import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import audit_tool

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_MODULES = {"lexicon", "tag", "checker", "ingest"}
FORBIDDEN_TEXT = ["recipe_tag", "allergens_may", "ingredient_allergen", "recipe_ingredient_norm", "data/lexicon",
                  "checker", "chunk", "split"]


def test_the_tool_imports_nothing_that_knows_the_tags():
    tree = ast.parse((ROOT / "scripts" / "audit_tool.py").read_text(encoding="utf-8"))
    imported = {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not imported & FORBIDDEN_MODULES


def test_the_tool_and_its_page_never_mention_tags_or_the_split():
    code = "\n".join(line for line in (ROOT / "scripts" / "audit_tool.py").read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))
    code = code.split('"""', 2)[2]  # skip the module docstring, which explains what the tool does not read
    page = (ROOT / "scripts" / "audit_tool.html").read_text(encoding="utf-8")
    for word in FORBIDDEN_TEXT:
        assert word not in code, word
        assert word not in page, word


@pytest.fixture
def client(recipes, test_db_url, tmp_path, monkeypatch):
    sample = tmp_path / "sample.csv"
    with open(sample, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sample_order", "recipe_id", "category", "split"])
        w.writerows([[1, 2, "Main", "holdout"], [2, 1, "Main", "dev"]])
    monkeypatch.setattr(audit_tool, "SAMPLE", sample)
    monkeypatch.setattr(audit_tool, "GOLD", tmp_path / "gold.csv")
    return TestClient(audit_tool.create_app(test_db_url))


def test_the_api_returns_only_the_raw_recipe(client):
    d = client.get("/api/recipe/1").json()
    assert set(d) == audit_tool.RECIPE_FIELDS
    assert d["title"] == "Toast" and d["ingredients"] == ["2 slices bread"] and d["saved"] is None


ALL_NO = {k: "no" for k in audit_tool.ALLERGENS + audit_tool.DIETS}


def test_saving_requires_every_field_and_resumes_at_the_next_open_recipe(client):
    assert client.post("/api/label/1", json={"labels": {"milk": "no"}}).status_code == 422
    s = client.post("/api/label/1", json={"labels": {**ALL_NO, "wheat": "yes", "vegetarian": "yes"}, "note": " ok "}).json()
    assert s == {"total": 2, "labeled": 1, "next": 2}
    saved = client.get("/api/recipe/1").json()["saved"]
    assert saved["labels"]["wheat"] == "yes" and saved["note"] == "ok"


def test_a_relabel_replaces_the_earlier_row(client):
    client.post("/api/label/2", json={"labels": ALL_NO})
    client.post("/api/label/2", json={"labels": {**ALL_NO, "crustacean_shellfish": "yes"}})
    assert client.get("/api/recipe/2").json()["saved"]["labels"]["crustacean_shellfish"] == "yes"
