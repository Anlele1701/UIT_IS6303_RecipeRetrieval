import csv
import json

import pytest

import significance

STRATEGIES = ["fixed", "semantic", "sentence"]
QUERY_IDS = ["q001", "q002", "q003", "q004"]


def write_run(folder, ranks, arm=None):
    """A run folder: per_query.csv from ranks[(config, variant, strategy, query id)], and settings.json."""
    folder.mkdir()
    (folder / "settings.json").write_text(json.dumps({"arm": arm}))
    with open(folder / "per_query.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["config", "variant", "strategy", "query_id", "rank"])
        for (c, v, s, q), rank in ranks.items():
            w.writerow([c, v, s, q, rank or ""])
    return folder


def full_run(tmp_path):
    ranks = {(c, "default", s, q): 1 if c == "hybrid" else 7
             for c in ("sparse", "dense", "fusion", "hybrid") for s in STRATEGIES for q in QUERY_IDS}
    return write_run(tmp_path / "full", ranks)


def test_identical_scores_differ_by_nothing():
    out = significance.paired_bootstrap([1, 0, 1], [1, 0, 1], resamples=100, seed=1)
    assert (out["diff"], out["ci_lo"], out["ci_hi"], out["p_raw"]) == (0, 0, 0, 1)


def test_a_config_that_always_wins_differs_with_no_doubt():
    out = significance.paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0], resamples=100, seed=1)
    assert (out["diff"], out["ci_lo"], out["ci_hi"], out["p_raw"]) == (1, 1, 1, 0)


def test_a_mixed_difference_has_a_ci_around_it_and_a_p_between_0_and_1():
    a, b = [1, 1, 1, 0, 1, 0, 1, 1], [0, 1, 0, 0, 1, 1, 0, 1]
    out = significance.paired_bootstrap(a, b, resamples=2000, seed=1)
    assert out["diff"] == pytest.approx(0.25)
    assert out["ci_lo"] < 0.25 < out["ci_hi"] and 0 < out["p_raw"] < 1


def test_a_full_run_tests_the_15_fixed_comparisons_on_r5_and_mrr(tmp_path):
    data = json.loads(significance.run(full_run(tmp_path), resamples=50).read_text())
    names = {(c["a"]["config"], c["a"]["strategy"], c["b"]["config"], c["b"]["strategy"])
             for c in data["comparisons"]}
    per_strategy = {(a, s, b, s) for s in STRATEGIES
                    for a, b in [("hybrid", "fusion"), ("fusion", "sparse"), ("fusion", "dense"), ("sparse", "dense")]}
    across = {("hybrid", "fixed", "hybrid", "semantic"), ("hybrid", "fixed", "hybrid", "sentence"),
              ("hybrid", "semantic", "hybrid", "sentence")}
    assert names == per_strategy | across and len(names) == 15
    assert {c["metric"] for c in data["comparisons"]} == {"recall@5", "mrr"} and len(data["comparisons"]) == 30
    hybrid_vs_fusion = next(c for c in data["comparisons"] if c["a"]["config"] == "hybrid"
                            and c["b"]["config"] == "fusion" and c["metric"] == "mrr")
    assert hybrid_vs_fusion["diff"] == pytest.approx(1 - 1 / 7)
    assert "p_holm" not in hybrid_vs_fusion  # Holm spans runs, so the bundle applies it
    assert (data["seed"], data["resamples"]) == (significance.SEED, 50)


def test_a_full_run_gives_each_config_its_own_ci(tmp_path):
    data = json.loads(significance.run(full_run(tmp_path), resamples=50).read_text())
    assert len(data["intervals"]) == 4 * 3 * 2  # configs x strategies x metrics
    sparse = next(i for i in data["intervals"] if i["config"] == "sparse" and i["metric"] == "recall@5")
    assert (sparse["mean"], sparse["ci_lo"], sparse["ci_hi"]) == (0, 0, 0)  # rank 7 is outside the top 5


def test_an_ablation_run_tests_the_arm_against_its_default_per_config_and_strategy(tmp_path):
    ranks = {("fusion", v, s, q): 2 if v == "arm" else 9 for v in ("default", "arm") for s in STRATEGIES
             for q in QUERY_IDS}
    run = write_run(tmp_path / "arm", ranks, arm={"key": "rrf-k-10", "configs": ["fusion"], "set": {"rrf_k": 10}})
    data = json.loads(significance.run(run, resamples=50).read_text())
    assert {(c["a"]["variant"], c["b"]["variant"], c["a"]["strategy"]) for c in data["comparisons"]} == {
        ("arm", "default", s) for s in STRATEGIES}
    assert len(data["comparisons"]) == 3 * 2
    assert all(c["a"]["config"] == c["b"]["config"] == "fusion" for c in data["comparisons"])


def test_the_same_run_gives_the_same_numbers(tmp_path):
    run = full_run(tmp_path)
    first = json.loads(significance.run(run, resamples=50).read_text())
    assert json.loads(significance.run(run, resamples=50).read_text()) == first

