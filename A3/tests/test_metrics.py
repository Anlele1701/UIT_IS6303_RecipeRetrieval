import math

import pytest

from metrics import dedupe, latency_summary, metrics_table, rank_of


def row(table, config="sparse", strategy="semantic"):
    return table[config, strategy]


def test_rank_1_rank_7_and_a_miss_give_the_hand_worked_values():
    relevant = {"q1": 10, "q2": 20, "q3": 30}
    runs = {
        ("sparse", "semantic", "q1"): [10, 1, 2],                  # rank 1
        ("sparse", "semantic", "q2"): [1, 2, 3, 4, 5, 6, 20, 7],   # rank 7
        ("sparse", "semantic", "q3"): [1, 2, 3],                   # not found
    }
    r = row(metrics_table(relevant, runs))
    assert r["recall@5"] == pytest.approx(1 / 3)
    assert r["recall@10"] == pytest.approx(2 / 3)
    assert r["recall@20"] == pytest.approx(2 / 3)
    assert r["mrr"] == pytest.approx((1 + 1 / 7 + 0) / 3)
    assert r["ndcg@5"] == pytest.approx(1 / 3)                      # only rank 1 counts: 1/log2(2) = 1
    assert r["ndcg@10"] == pytest.approx((1 + 1 / math.log2(8)) / 3)  # rank 7: 1/log2(8) = 1/3
    assert r["queries"] == 3


def test_a_duplicate_recipe_counts_once_at_its_first_rank():
    # Chunks of Recipe 5 fill positions 1-3; the relevant Recipe 9 is the 2nd unique Recipe.
    assert rank_of(9, [5, 5, 5, 9, 9]) == 2
    r = row(metrics_table({"q1": 9}, {("dense", "fixed", "q1"): [5, 5, 5, 9, 9]}), "dense", "fixed")
    assert r["mrr"] == 0.5
    assert r["ndcg@5"] == pytest.approx(1 / math.log2(3))


def test_an_empty_result_and_a_missing_query_are_misses_and_averages_cover_every_query():
    relevant = {"q1": 1, "q2": 2, "q3": 3}
    runs = {("sparse", "semantic", "q1"): [1], ("sparse", "semantic", "q2"): []}  # q3 never ran
    r = row(metrics_table(relevant, runs))
    assert r["recall@20"] == pytest.approx(1 / 3) and r["mrr"] == pytest.approx(1 / 3)


def test_only_the_top_20_unique_recipes_count():
    ranked = [*range(100, 120), 7]  # Recipe 7 is the 21st unique Recipe
    assert rank_of(7, ranked) is None
    assert rank_of(7, [100, 100, *range(101, 119), 7]) == 20
    assert len(dedupe(range(50))) == 20


def test_each_config_and_strategy_gets_its_own_row():
    runs = {("sparse", "a", "q1"): [1], ("dense", "a", "q1"): [2, 1], ("sparse", "b", "q1"): []}
    table = metrics_table({"q1": 1}, runs)
    assert list(table) == [("sparse", "a"), ("dense", "a"), ("sparse", "b")]
    assert [r["mrr"] for r in table.values()] == [1.0, 0.5, 0.0]


def test_latency_summary_is_p50_and_p95():
    assert latency_summary(range(1, 101)) == {"p50_ms": 50.5, "p95_ms": pytest.approx(95.05)}
    assert latency_summary([]) == {"p50_ms": 0.0, "p95_ms": 0.0}
