"""Integrity of the committed lexicon files in data/lexicon/."""

import csv

from lexicon.normalize import LEXICON, key
from lexicon.tagger import ALLERGENS, GROUP_PRIORITY, Rules


def rows(name):
    with open(LEXICON / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_allergens_are_the_fda_nine():
    assert [r["code"] for r in rows("allergens.csv")] == ALLERGENS


def test_rules_use_known_allergens_and_groups():
    Rules.from_csv()  # raises on an unknown allergen code
    groups = {r["group"] for r in rows("rules.csv") if r["phrase"] and not r["phrase"].startswith("#")}
    assert groups <= set(GROUP_PRIORITY) | {""}


def test_ingredients_are_lowercase_and_no_synonym_points_to_two_canonicals():
    seen = {}
    for r in rows("ingredients.csv"):
        assert r["canonical"] == r["canonical"].lower()
        for s in [r["canonical"], *filter(None, r["synonyms"].split("|"))]:
            k = key(s)
            assert seen.setdefault(k, r["canonical"]) == r["canonical"], f"{s!r} maps to two canonicals"


def test_allergen_map_matches_ingredients_and_codes():
    canonicals = {r["canonical"] for r in rows("ingredients.csv")}
    for r in rows("allergen_map.csv"):
        assert r["canonical"] in canonicals
        assert set(r["allergens"].split("|")) <= set(ALLERGENS)
        assert r["kind"] in {"direct", "hidden"}


def test_vi_aliases_point_at_known_targets():
    if not (LEXICON / "vi_alias.csv").exists():
        return
    canonicals = {r["canonical"] for r in rows("ingredients.csv")}
    for r in rows("vi_alias.csv"):
        assert r["alias"] == r["alias"].lower()
        if r["target_type"] == "allergen":
            assert r["target"] in ALLERGENS, r
        else:
            assert r["target_type"] == "ingredient" and r["target"] in canonicals, r
