import eval_allergen as ea

NO = {g: "no" for g in ea.ALLERGENS} | {"vegetarian": "yes", "vegan": "yes", "note": ""}
SAMPLE = [{"recipe_id": "1", "split": "dev"}, {"recipe_id": "2", "split": "dev"},
          {"recipe_id": "3", "split": "holdout"}, {"recipe_id": "4", "split": "holdout"}]
LABELS = {1: {**NO, "milk": "yes", "vegan": "no"},          # butter cake
          2: {**NO, "milk": "maybe", "vegan": "maybe"},     # chocolate chips
          3: {**NO, "fish": "yes", "vegetarian": "no", "vegan": "no"},
          4: dict(NO)}
TAGS = {1: {"allergens": ["milk"], "allergens_may": [], "diet_flags": ["vegetarian"], "diet_may": []},
        2: {"allergens": [], "allergens_may": ["milk"], "diet_flags": ["vegetarian", "vegan"], "diet_may": ["vegan"]},
        3: {"allergens": [], "allergens_may": [], "diet_flags": ["vegetarian", "vegan"], "diet_may": []},  # missed fish
        4: {"allergens": [], "allergens_may": [], "diet_flags": ["vegetarian", "vegan"], "diet_may": []}}
VERDICTS = {(1, "allergen:milk"): "yes", (2, "allergen:milk"): "unsure", (3, "allergen:milk"): "no",
            (4, "allergen:milk"): "no", (3, "allergen:fish"): "yes", (3, "diet:vegetarian"): "yes"}


def run():
    return ea.compute(SAMPLE, LABELS, TAGS, VERDICTS)


def test_milk_precision_and_recall_under_both_label_variants():
    res = run()
    yes = res["pr"]["label_yes"]["all"]
    assert (yes["tagger_definite"]["milk"]["tp"], yes["tagger_definite"]["milk"]["fp"]) == (1, 0)
    assert yes["tagger_with_possible"]["milk"]["fp"] == 1  # recipe 2 is only "maybe"
    both = res["pr"]["label_yes_or_maybe"]["all"]
    assert both["tagger_definite"]["milk"]["fn"] == 1 and both["tagger_with_possible"]["milk"]["recall"]["value"] == 1.0


def test_checker_strict_counts_unsure_as_contains_and_lenient_does_not():
    yes = run()["pr"]["label_yes_or_maybe"]["all"]
    assert yes["checker_strict"]["milk"]["recall"]["value"] == 1.0
    assert yes["checker_lenient"]["milk"]["recall"]["value"] == 0.5


def test_diets_count_breaking_the_diet_as_positive():
    yes = run()["pr"]["label_yes"]["holdout"]
    assert yes["tagger_definite"]["vegetarian"]["fn"] == 1  # recipe 3 has fish but was flagged vegetarian
    assert yes["checker_strict"]["vegetarian"]["tp"] == 1


def test_splits_and_disagreement():
    res = run()
    assert res["recipes"] == {"dev": 2, "holdout": 2, "all": 4}
    # recipe 3: checker says fish, tagger missed it; 1, 2, 4 have no fish verdict, i.e. unsure = contains (strict)
    assert res["disagreement"]["fish"] == {"both": 0, "tagger_only": 0, "checker_only": 4, "neither": 0}


def test_errors_list_the_dev_split_only():
    errs = ea.errors(SAMPLE, LABELS, TAGS, VERDICTS, {})
    assert errs["fish"]["counts"]["tagger_fn"] == 0  # the fish miss is in the holdout
    assert all(r in (1, 2) for e in errs.values() for k, v in e.items() if k != "counts" for r in v)


def test_a_missing_checker_verdict_is_unsure():
    yes = run()["pr"]["label_yes"]["all"]
    # no verdict stored for recipes 1, 2, 4 on fish: strict counts them as contains -> false positives
    assert yes["checker_strict"]["fish"]["fp"] == 3 and yes["checker_lenient"]["fish"]["fp"] == 0
