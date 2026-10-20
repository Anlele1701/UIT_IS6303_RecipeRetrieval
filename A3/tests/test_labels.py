"""The hand labels in eval/ must cover exactly the queries they describe, with known labels only."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_RUN = ROOT / "eval" / "runs" / "20260928-122309"


def read(name):
    with open(ROOT / "eval" / name, newline="") as f:
        return list(csv.DictReader(f))


def test_every_hand_rewrite_has_one_reason():
    edited = {q["query_id"] for q in map(json.loads, open(ROOT / "eval" / "queries.jsonl")) if "edited_from" in q}
    rows = read("query_edits.csv")
    assert sorted(r["query_id"] for r in rows) == sorted(edited)
    assert {r["reason"] for r in rows} <= {"wrong facts", "broken", "too vague", "copies title", "odd wording"}


def test_every_query_all_configs_miss_on_all_strategies_has_one_error_group():
    with open(REPORT_RUN / "per_query.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    found = {r["query_id"] for r in rows if r["rank"]}
    missed = {r["query_id"] for r in rows} - found
    labels = read("error_groups.csv")
    assert sorted(r["query_id"] for r in labels) == sorted(missed)
    assert {r["group"] for r in labels} <= {"near-duplicate", "opaque title", "lexical trap", "other"}
