"""Adjudication of the checker's "yes" verdicts: the automatic step and the human labels (no DB, no model)."""

import adjudicate as adj
import checker

LINES = ["2 (6 ounce) fillets salmon (1-inch thick)", "3 tablespoons  Worcestershire sauce", "1 cup flour"]


def v(contains, ev, ok=True):
    return checker.Verdict(contains, ev, ok)


def test_a_flagged_or_non_verbatim_yes_is_dropped_from_the_adjudicated_count():
    flagged = adj.score(1, "allergen:wheat", v("yes", "- 2 tablespoons grated Parmesan cheese", False), LINES, {})
    loose = adj.score(1, "allergen:wheat", v("yes", "some wheat flour"), LINES, {})
    assert (flagged.status, flagged.raw, flagged.adjudicated) == ("dropped_flagged", True, False)
    assert (loose.status, loose.raw, loose.adjudicated) == ("dropped_not_verbatim", True, False)


def test_a_verbatim_yes_waits_for_a_reviewer_and_counts_meanwhile():
    s = adj.score(1, "allergen:wheat", v("yes", "2 (6 ounce) FILLETS salmon"), LINES, {})
    assert (s.status, s.adjudicated) == ("pending", True)


def test_spaces_and_case_do_not_matter_for_verbatim():
    assert adj.verbatim("3 tablespoons worcestershire sauce", LINES)


def test_a_reviewer_label_decides():
    labels = {(1, "allergen:wheat"): {"violation": "no"}, (2, "allergen:wheat"): {"violation": "yes"}}
    no = adj.score(1, "allergen:wheat", v("yes", "3 tablespoons Worcestershire sauce"), LINES, labels)
    yes = adj.score(2, "allergen:wheat", v("yes", "1 cup flour"), LINES, labels)
    assert (no.status, no.adjudicated) == ("rejected", False) and (yes.status, yes.adjudicated) == ("confirmed", True)


def test_no_and_unsure_never_count():
    assert not adj.score(1, "allergen:egg", v("no", ""), LINES, {}).raw
    assert not adj.score(1, "allergen:egg", v("unsure", ""), LINES, {}).raw


def test_summary_counts_recipes_once():
    scored = [adj.Scored(1, "allergen:wheat", "yes", "x", "pending", True, True),
              adj.Scored(1, "allergen:milk", "yes", "x", "dropped_flagged", True, False),
              adj.Scored(2, "allergen:milk", "yes", "x", "rejected", True, False)]
    s = adj.summary(scored, recipes=5)
    assert (s["violating_raw"], s["violating_adjudicated"], s["pending"]) == (2, 1, 1)


def test_the_committed_labels_load():
    labels = adj.load_labels()
    assert labels[(2920, "allergen:wheat")]["violation"] == "no"
