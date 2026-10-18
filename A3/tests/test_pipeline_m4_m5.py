"""M4 on the test DB (conftest RECIPES: 1 Garlic Shrimp, 2 Toast, 3 Tea) and M5 grouping."""

import numpy as np
import pytest

import ingest
import tag
from api import retrieval
from api.filters import SearchParams
from api.pipeline import m4_retrieve as m4
from api.pipeline.m5_postprocess import cards, top_recipes
from api.pipeline.schemas import Constraints
from api.retrieval import Candidate

QVEC = "[" + ",".join(["0.036"] * 768) + "]"


@pytest.fixture
def tagged(recipes, fake_embed):
    report, tables = tag.tag_all(recipes)
    tag.write_tables(recipes, tables)
    ingest.run(recipes, ["chunk", "sentence"])
    return recipes


def recipe_ids(chunks):
    return {c.recipe_id for c in chunks}


def test_no_constraint_matches_a1_fused_candidates(tagged):
    a1 = retrieval.fused_candidates(tagged, SearchParams(q="garlic shrimp", strategy="sentence", k=50), QVEC)
    got = m4.search(tagged, "garlic shrimp", QVEC, Constraints(), filter_on=False, norm=True, strategy="sentence")
    assert [c.chunk_id for c in got] == [c.chunk_id for c in a1]


def test_the_allergen_filter_drops_tagged_recipes_inside_the_index(tagged):
    got = m4.search(tagged, "garlic shrimp", QVEC, Constraints(allergens_exclude=["crustacean_shellfish"]),
                    filter_on=True, norm=True, strategy="sentence")
    assert 1 not in recipe_ids(got) and recipe_ids(got)


def test_s_norm_filters_raw_lines_with_ilike(tagged):
    got = m4.search(tagged, "garlic shrimp", QVEC, Constraints(ingredients_exclude=["shrimp"]),
                    filter_on=True, norm=False, strategy="sentence")
    assert 1 not in recipe_ids(got)


def test_s_filter_writes_constraints_into_the_query_instead():
    c = Constraints(allergens_exclude=["peanut"], diet="vegan", max_total_minutes=30, ingredients_include=["tofu"])
    assert m4.query_text("curry", c, filter_on=False) == "curry tofu without peanut, vegan, ready in 30 minutes"
    assert m4.query_text("curry", c, filter_on=True) == "curry tofu"


def test_possible_tags_and_unknown_strict_in_the_conditions():
    cond, params = m4.conditions(Constraints(allergens_exclude=["milk"]), norm=True, unknown_strict=True)
    text = cond.as_string()
    assert "allergens @@@ pdb.term_set" in text and "has_unknown = false" in text and "allergens_may" not in text


def test_m5_groups_chunks_by_recipe_keeping_the_best_and_k():
    chunks = [Candidate(i, rid, "step", i, f"c{i}", s) for i, (rid, s) in enumerate([(7, .9), (8, .8), (7, .7), (9, .6)])]
    assert top_recipes("q", chunks, scorer=None, k=2, use_rerank=False) == [(7, .9), (8, .8)]


def test_m5_rerank_reorders_before_grouping():
    chunks = [Candidate(1, 7, "step", 1, "a", .9), Candidate(2, 8, "step", 1, "b", .1)]
    assert top_recipes("q", chunks, scorer=lambda q, texts: np.array([0.0, 5.0]), k=2)[0][0] == 8


def test_cards_carry_definite_and_possible_tags(tagged):
    c = cards(tagged, [(1, 0.5)])[0]
    assert c.title == "Garlic Shrimp" and c.allergens == ["crustacean_shellfish"] and c.ingredients[0] == "1 lb shrimp"
