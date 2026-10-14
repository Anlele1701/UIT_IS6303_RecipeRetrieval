"""Before/after check for a rebuild that must not change retrieval (e.g. `ingest.py retag`).

    uv run scripts/compare_runs.py eval/runs/<before> eval/runs/<after> --out eval/m1_retag_check.json

Compares the configs both runs share, per strategy: every metric, each query's rank of the first right
Recipe, and each query's top-20 Recipe list. Writes the JSON named by --out; nothing is typed by hand.
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS = ["recall@5", "recall@10", "recall@20", "mrr", "ndcg@5", "ndcg@10"]


def per_query(run: Path) -> dict:
    with open(run / "per_query.csv", newline="", encoding="utf-8") as f:
        return {(r["config"], r["strategy"], r["query_id"]): r for r in csv.DictReader(f)}


def metrics(run: Path) -> dict:
    return {(m["config"], m["strategy"]): m for m in json.loads((run / "metrics.json").read_text(encoding="utf-8"))
            if m.get("variant", "default") == "default"}


def compare(before: Path, after: Path) -> dict:
    mb, ma, pb, pa = metrics(before), metrics(after), per_query(before), per_query(after)
    out = {"checked_at": datetime.now().isoformat(timespec="seconds"),
           "before": before.relative_to(ROOT).as_posix(), "after": after.relative_to(ROOT).as_posix(),
           "probe": {"before": json.loads((before / "settings.json").read_text(encoding="utf-8")).get("vector_cluster_max_probe"),
                     "after": json.loads((after / "settings.json").read_text(encoding="utf-8")).get("vector_cluster_max_probe")},
           "configs": {}}
    for key in sorted(mb.keys() & ma.keys()):
        qs = [k for k in pa if k[:2] == key and k in pb]
        changed = [k[2] for k in qs if pb[k]["top_recipe_ids"] != pa[k]["top_recipe_ids"]]
        out["configs"]["/".join(key)] = {
            "metric_delta": {m: round(ma[key][m] - mb[key][m], 6) for m in METRICS},
            "queries": len(qs),
            "same_rank": sum(pb[k]["rank"] == pa[k]["rank"] for k in qs),
            "same_top20": len(qs) - len(changed),
            "top20_changed": changed,
        }
    out["identical_metrics"] = all(all(v == 0 for v in c["metric_delta"].values()) for c in out["configs"].values())
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    res = compare(a.before.resolve(), a.after.resolve())
    a.out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
