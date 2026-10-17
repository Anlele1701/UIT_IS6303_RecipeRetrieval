"""Rule tables: refused when malformed, and checked against the ingredient table and chunk columns (test DB)."""

import shutil

import pytest

from api.patient import rules


@pytest.fixture
def folder(tmp_path):
    for name in rules.RULE_SET_FILES:
        shutil.copy(rules.RULES_DIR / name, tmp_path / name)
    return tmp_path


def append(folder, name, line):
    with open(folder / name, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def test_the_committed_rules_load(folder):
    rs = rules.load_rules(folder)
    assert set(rs.allergy) >= {"412071004", "735029006"} and len(rs.drug) == 3
    assert rs.version == rules.ruleset_version()


def test_unknown_allergen_group_is_refused(folder):
    append(folder, "allergy_substance.csv", "999,Kiwi (substance),kiwi_group,,true,v1,")
    with pytest.raises(rules.RuleError, match="unknown allergen group"):
        rules.load_rules(folder)


def test_drug_row_without_source_is_refused(folder):
    append(folder, "drug_food.csv", "metformin,warn,,x,,v1")
    with pytest.raises(rules.RuleError, match="no source"):
        rules.load_rules(folder)


def test_filter_on_a_nutrient_without_column_becomes_a_warning(folder):
    append(folder, "condition_nutrient.csv", "1,X,phosphorus_mg,max,800,mg,filter,s,v1,")
    rs = rules.load_rules(folder)
    row = [r for r in rs.nutrient if r.conditions == ("1",)][0]
    assert row.mode == "warn" and any("phosphorus_mg" in m for m in rs.log)


def test_version_changes_with_any_rule_file(folder):
    before = rules.ruleset_version(folder)
    append(folder, "prompt_vitals.csv", "8867-4,Heart rate,v1")
    assert rules.ruleset_version(folder) != before


def test_db_check_refuses_an_unknown_ingredient(folder, db):
    db.execute("TRUNCATE ingredient RESTART IDENTITY CASCADE")
    db.execute("INSERT INTO ingredient (canonical_name) VALUES ('grapefruit')")
    rs = rules.load_rules(folder)
    with pytest.raises(rules.RuleError, match="not in the ingredient table"):
        rules.validate_against_db(rs, db)  # the molluscs and vitamin K greens are missing in the test DB


def test_db_check_refuses_a_missing_filter_column(folder, db, monkeypatch):
    names = sorted({n for a in rules.load_rules(folder).allergy.values() for n in a.extra_ingredients}
                   | {n for d in rules.load_rules(folder).drug for n in d.targets})
    db.execute("TRUNCATE ingredient RESTART IDENTITY CASCADE")
    for n in names:
        db.execute("INSERT INTO ingredient (canonical_name) VALUES (%s)", [n])
    rs = rules.load_rules(folder)
    rules.validate_against_db(rs, db)  # the test DB has migration 006's columns: passes
    monkeypatch.setitem(rules.NUTRIENT_COLUMN, "sodium_mg", "sodium_per_meal")
    with pytest.raises(rules.RuleError, match="filter columns missing"):
        rules.validate_against_db(rs, db)
