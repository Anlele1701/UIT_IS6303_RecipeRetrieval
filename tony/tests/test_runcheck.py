import csv

import runcheck


def write_run(folder, rows, variant=True):
    """A run folder holding just per_query.csv. rows: (config, variant, strategy, query_id, rank)."""
    folder.mkdir()
    with open(folder / "per_query.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["config", "variant", "strategy", "query_id", "rank"] if variant
                   else ["config", "strategy", "query_id", "rank"])
        for c, v, s, q, r in rows:
            w.writerow([c, v, s, q, r] if variant else [c, s, q, r])
    return folder


REPORT = [("sparse", "default", "fixed", "q001", "1"), ("hybrid", "default", "fixed", "q001", "3"),
          ("hybrid", "default", "fixed", "q002", "")]


def report_run(tmp_path):
    return write_run(tmp_path / "report", REPORT, variant=False)  # the Report run predates the variant column


def test_a_timing_repeat_with_the_same_ranks_passes(tmp_path):
    assert runcheck.rank_mismatches(report_run(tmp_path), write_run(tmp_path / "repeat", REPORT)) == []


def test_a_changed_rank_is_named_by_config_strategy_and_query(tmp_path):
    changed = [*REPORT[:2], ("hybrid", "default", "fixed", "q002", "20")]
    assert runcheck.rank_mismatches(report_run(tmp_path), write_run(tmp_path / "repeat", changed)) == [
        "hybrid/fixed/q002: report miss, this run 20"]


def test_an_ablation_run_is_checked_on_its_default_rows_and_its_own_configs_only(tmp_path):
    ablation = [("hybrid", "default", "fixed", "q001", "3"), ("hybrid", "arm", "fixed", "q001", "1"),
                ("hybrid", "default", "fixed", "q002", ""), ("hybrid", "arm", "fixed", "q002", "4")]
    assert runcheck.rank_mismatches(report_run(tmp_path), write_run(tmp_path / "arm", ablation)) == []


def test_a_missing_query_is_a_mismatch(tmp_path):
    assert runcheck.rank_mismatches(report_run(tmp_path), write_run(tmp_path / "short", REPORT[:2])) == [
        "hybrid/fixed/q002: report miss, this run absent"]


def test_a_limited_run_is_checked_on_the_queries_it_holds(tmp_path):
    short = write_run(tmp_path / "smoke", REPORT[:2])
    (short / "settings.json").write_text('{"limit": 1}')  # a quick `--limit` run, not a broken full one
    assert runcheck.rank_mismatches(report_run(tmp_path), short) == []
