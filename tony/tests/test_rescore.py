import csv
import json

import pytest

import rescore
from metrics import first_rank


def test_first_rank_takes_the_earliest_right_recipe_after_dedupe():
    assert first_rank({7, 3}, [1, 3, 3, 7]) == 2
    assert first_rank({9}, [1, 1, 2, 9]) == 3  # the duplicate 1 doesn't take a place
    assert first_rank({9}, [1, 2]) is None


def pq(query_id, recipe_id, top, rank, config="hybrid", kind="step"):
    return {"config": config, "strategy": "fixed", "query_id": query_id, "recipe_id": str(recipe_id),
            "rank": str(rank or ""), "best_kind": kind, "top_recipe_ids": " ".join(map(str, top))}


def test_a_judged_recipe_above_the_labelled_one_moves_the_rank_up_and_clears_best_kind():
    rows = [pq("q1", 10, [5, 10], 2), pq("q2", 20, [20, 6], 1)]
    got = rescore.rescore_rows(rows, {"q1": {10, 5}, "q2": {20, 6}})
    assert [(r["rank"], r["best_kind"]) for r in got] == [(1, ""), (1, "step")]


def test_qrels_without_the_labelled_recipe_fail():
    with pytest.raises(ValueError, match="q1"):
        rescore.rescore_rows([pq("q1", 10, [10], 1)], {"q1": {5}})


def test_metrics_are_recomputed_and_latency_is_kept():
    old = [{"config": "hybrid", "strategy": "fixed", "queries": 2, "recall@5": 0.0, "short_lists": 0,
            "latency_ms": {"total": {"p50_ms": 700.0, "p95_ms": 900.0}}}]
    rows = [{"config": "hybrid", "strategy": "fixed", "rank": 1}, {"config": "hybrid", "strategy": "fixed", "rank": ""}]
    (new,) = rescore.rescore_metrics(old, rows)
    assert new["recall@5"] == 0.5 and new["mrr"] == 0.5
    assert new["latency_ms"] == old[0]["latency_ms"]


def test_rescore_writes_a_full_run_folder_and_leaves_the_original_alone(tmp_path):
    run = tmp_path / "runs" / "20260101-000000"
    run.mkdir(parents=True)
    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps({"query_id": "q1", "text": "x", "recipe_id": 10, "recipe_title": "T",
                                   "word_overlap": 1.0}) + "\n")
    settings = {"query_set": str(queries), "strategies": ["fixed"], "arm": None}
    (run / "settings.json").write_text(json.dumps(settings))
    metrics_rows = [{"config": c, "strategy": "fixed", "queries": 1, "short_lists": 0,
                     "latency_ms": {"total": {"p50_ms": 1.0, "p95_ms": 1.0}}}
                    for c in ["sparse", "dense", "fusion", "hybrid"]]
    (run / "metrics.json").write_text(json.dumps(metrics_rows))
    with open(run / "per_query.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pq("q1", 10, [5, 10], 2)))
        w.writeheader()
        w.writerows(pq("q1", 10, [5, 10], 2, c) for c in ["sparse", "dense", "fusion", "hybrid"])
    original = (run / "per_query.csv").read_text()
    qrels = tmp_path / "qrels.csv"
    qrels.write_text("query_id,recipe_id,relevant,source,note\nq1,10,1,label,\nq1,5,1,judged,\nq1,6,0,judged,\n")

    dest = rescore.rescore(run, qrels, tmp_path / "pooled")

    assert (run / "per_query.csv").read_text() == original
    assert json.loads((dest / "metrics.json").read_text())[0]["mrr"] == 1.0
    assert json.loads((dest / "settings.json").read_text())["qrels_sha256"]
    for name in ["metrics.csv", "table.md", "significance.json", "failures.json"]:
        assert (dest / name).exists()
