import json

import pytest

import report_bundle


def test_the_committed_bundle_is_built_from_the_files_as_they_are_now():
    """Fails when a run folder, label file or the manifest changed after the bundle was built.

    Rebuild with `uv run python scripts/report_bundle.py`.
    """
    if not report_bundle.OUT.exists():
        pytest.fail(f"{report_bundle.OUT} is missing; build it with scripts/report_bundle.py")
    bundle = json.loads(report_bundle.OUT.read_text())
    manifest = json.loads(report_bundle.MANIFEST.read_text())
    expected = {report_bundle.rel(p): report_bundle.sha256(p) for p in report_bundle.input_files(manifest)}
    stale = sorted(p for p in expected.keys() | bundle["meta"]["input_hashes"].keys()
                   if expected.get(p) != bundle["meta"]["input_hashes"].get(p))
    assert not stale, f"bundle is stale for: {', '.join(stale)}"


def test_holm_scales_the_kth_smallest_p_and_keeps_the_order_monotone():
    assert report_bundle.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert report_bundle.holm([0.5, 0.9]) == [1.0, 1.0]  # capped at 1
    assert report_bundle.holm([]) == []


def row(config, strategy, p50, p95, variant="default"):
    return {"config": config, "strategy": strategy, "variant": variant,
            "latency_ms": {"total": {"p50_ms": p50, "p95_ms": p95}}}


def test_repeat_latency_takes_the_median_of_the_p50s_and_their_range():
    repeats = [[row("hybrid", "fixed", 700, 900), row("hybrid", "fixed", 1, 1, "arm")],
               [row("hybrid", "fixed", 800, 1100)],
               [row("hybrid", "fixed", 950, 1000)]]
    got = report_bundle.repeat_latency(repeats)[("hybrid", "fixed")]["total"]
    assert got == {"p50": 800, "p95": 1000, "p50_min": 700, "p50_max": 950}


def test_best_rows_marks_every_tie_per_strategy():
    rows = [{"config": "fusion", "strategy": "fixed", "recall@5": 0.7},
            {"config": "hybrid", "strategy": "fixed", "recall@5": 0.7},
            {"config": "sparse", "strategy": "sentence", "recall@5": 0.6},
            {"config": "hybrid", "strategy": "sentence", "recall@5": 0.65}]
    assert report_bundle.best_rows(rows) == {("fusion", "fixed"), ("hybrid", "fixed"), ("hybrid", "sentence")}


def test_the_overlap_histogram_keeps_full_overlap_in_its_own_bin():
    assert report_bundle.histogram([0.0, 0.05, 0.95, 0.999, 1.0, 1.0]) == [2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2]
