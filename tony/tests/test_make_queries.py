import json
from collections import Counter

import pytest

import make_queries as mq


class FakeLLM:
    """Returns scripted outputs in order and records the prompts it got."""

    def __init__(self, *outputs):
        self.outputs, self.prompts = list(outputs), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.outputs.pop(0)


def recipe(rid, title="Garlic Butter Shrimp"):
    return dict(id=rid, title=title, description="Shrimp in a buttery garlic sauce.",
                ingredients=["1 pound shrimp", "4 cloves garlic", "3 tablespoons butter"],
                directions="Melt butter. Add garlic and shrimp. Cook until pink.")


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


# --- sampling -------------------------------------------------------------------

PAIRS = [(i, "desserts") for i in range(1, 601)] + [(i, "salad") for i in range(601, 901)] + \
        [(i, "drinks") for i in range(901, 1001)]


def test_same_seed_gives_the_same_sample_whatever_the_input_order():
    first = mq.sample_recipes(PAIRS, 30, seed=7)
    assert mq.sample_recipes(list(reversed(PAIRS)), 30, seed=7) == first
    assert mq.sample_recipes(PAIRS, 30, seed=8) != first


def test_sample_is_stratified_by_category():
    cat = dict(PAIRS)
    ids = mq.sample_recipes(PAIRS, 30, seed=7)
    assert len(set(ids)) == 30
    assert Counter(cat[i] for i in ids) == {"desserts": 18, "salad": 9, "drinks": 3}


def test_sample_fills_the_exact_size_when_shares_dont_divide_evenly():
    pairs = [(1, "a"), (2, "a"), (3, "b"), (4, "b"), (5, "c")]
    assert len(mq.sample_recipes(pairs, 4, seed=1)) == 4


# --- generation -----------------------------------------------------------------

def test_prompt_has_title_description_and_ingredients():
    prompt = mq.build_prompt(recipe(1))
    for part in ["Garlic Butter Shrimp", "buttery garlic sauce", "4 cloves garlic"]:
        assert part in prompt


def test_title_is_rejected_and_retried(tmp_path):
    out = tmp_path / "q.jsonl"
    llm = FakeLLM('"Garlic butter shrimp."', "quick shrimp dinner with garlic")
    assert mq.build_query_set([recipe(1)], llm, "fake", out) == (1, [])
    assert len(llm.prompts) == 2
    [row] = read(out)
    assert row["text"] == "quick shrimp dinner with garlic"


def test_a_query_with_every_title_word_counts_as_repeating_it():
    assert mq.rejection("baked honey sriracha salmon flavorful", "Baked Honey Sriracha Salmon") == "repeats the title"
    assert mq.rejection("sweet sriracha salmon", "Baked Honey Sriracha Salmon") is None
    assert mq.rejection("chicken in olive herb sauce", "Chicken and Olives") is None  # short titles may appear


def test_a_retry_tells_the_llm_why_its_last_output_was_rejected(tmp_path):
    llm = FakeLLM("garlic butter shrimp dinner", "shrimp in buttery sauce")
    mq.build_query_set([recipe(1)], llm, "fake", tmp_path / "q.jsonl")
    assert "garlic butter shrimp dinner" not in llm.prompts[0]
    assert '"garlic butter shrimp dinner", which was rejected (repeats the title)' in llm.prompts[1]


def test_recipe_is_skipped_after_three_bad_outputs(tmp_path, capsys):
    out = tmp_path / "q.jsonl"
    llm = FakeLLM("", "word " * 13, "Garlic Butter Shrimp", "never asked")
    assert mq.build_query_set([recipe(1)], llm, "fake", out) == (0, [1])
    assert len(llm.prompts) == 3
    assert read(out) == []
    assert "skipped recipe 1" in capsys.readouterr().err


def test_each_line_has_the_query_set_fields(tmp_path):
    out = tmp_path / "q.jsonl"
    mq.build_query_set([recipe(1), recipe(2, "Lemon Bars")], FakeLLM("shrimp garlic", "tangy lemon dessert"),
                       "fake-model", out)
    assert read(out)[1] == {"query_id": "q002", "text": "tangy lemon dessert", "recipe_id": 2,
                            "recipe_title": "Lemon Bars", "word_overlap": 0.333, "model": "fake-model"}


def test_rerun_skips_recipes_that_already_have_a_query(tmp_path):
    out = tmp_path / "q.jsonl"
    mq.build_query_set([recipe(1)], FakeLLM("shrimp in garlic sauce"), "fake", out)
    llm = FakeLLM("tangy lemon dessert")
    assert mq.build_query_set([recipe(1), recipe(2, "Lemon Bars")], llm, "fake", out) == (1, [])
    assert len(llm.prompts) == 1
    assert [(r["query_id"], r["recipe_id"]) for r in read(out)] == [("q001", 1), ("q002", 2)]


# --- word overlap ---------------------------------------------------------------

def test_word_overlap_drops_stopwords_and_matches_stems():
    text = mq.recipe_text(recipe(1))
    # content words: shrimp, cook, pink, noodl; "cooked"~"cook", "the/with/for" dropped
    assert mq.word_overlap("the shrimp cooked with pink noodles", text) == 0.75
    assert mq.word_overlap("the of with", text) == 0.0


def test_word_overlap_ignores_accents():
    assert mq.word_overlap("jalapeño dip", "Corn dip with 1 jalapeno pepper") == 1.0
    assert mq.content_stems("sautéed") == mq.content_stems("sauteed")


# --- robustness -----------------------------------------------------------------

def test_a_search_label_on_its_own_line_is_not_an_empty_answer():
    assert mq.clean("Search:\ncreamy clam soup") == "creamy clam soup"
    assert mq.clean('Search: "creamy clam soup."') == "creamy clam soup"


def test_resume_drops_a_line_cut_off_by_a_crash(tmp_path):
    out = tmp_path / "q.jsonl"
    mq.build_query_set([recipe(1)], FakeLLM("shrimp in garlic sauce"), "fake", out)
    out.write_text(out.read_text() + '{"query_id": "q002", "te')
    mq.build_query_set([recipe(1), recipe(2, "Lemon Bars")], FakeLLM("tangy lemon dessert"), "fake", out)
    assert [r["query_id"] for r in read(out)] == ["q001", "q002"]


def test_resume_refuses_a_file_built_from_a_different_sample(tmp_path):
    out = tmp_path / "q.jsonl"
    mq.build_query_set([recipe(1), recipe(2, "Lemon Bars")], FakeLLM("shrimp in garlic sauce", "tangy lemon dessert"),
                       "fake", out)
    with pytest.raises(SystemExit, match="different sample"):
        mq.build_query_set([recipe(2, "Lemon Bars"), recipe(3)], FakeLLM(), "fake", out)
