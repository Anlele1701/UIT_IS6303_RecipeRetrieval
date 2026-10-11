"""M0 reproduction check: a new Evaluation run against A1's reference run (eval/a1_reference).

    uv run scripts/compare_a1.py eval/runs/<timestamp>

Writes eval/m0_reproduction.json and docs/m0_reproduction.md; nothing is typed by hand.
Quality metrics are judged against a tolerance; latency is recorded only, since the machine differs.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "eval" / "a1_reference"
OUT_JSON = ROOT / "eval" / "m0_reproduction.json"
OUT_MD = ROOT / "docs" / "m0_reproduction.md"
METRICS = ["recall@5", "recall@10", "mrr", "ndcg@10"]
TOLERANCE = {"fusion": 0.01, "hybrid": 0.015}  # |delta| allowed per metric (re-embedding + ANN noise)
STRATEGY = "semantic"


def rows(run: Path) -> dict[str, dict]:
    return {m["config"]: m for m in json.loads((run / "metrics.json").read_text(encoding="utf-8"))
            if m["strategy"] == STRATEGY and m.get("variant", "default") == "default"}


def compare(run: Path) -> dict:
    ref, new = rows(REFERENCE), rows(run)
    out = {"checked_at": datetime.now().isoformat(timespec="seconds"), "strategy": STRATEGY,
           "reference_run": "A1 eval/pooled/20261006-224100", "new_run": (run.relative_to(ROOT) if run.is_relative_to(ROOT) else run).as_posix(),
           "reference_settings": json.loads((REFERENCE / "settings.json").read_text(encoding="utf-8")),
           "new_settings": json.loads((run / "settings.json").read_text(encoding="utf-8")),
           "tolerance": TOLERANCE, "configs": {}}
    for config, tol in TOLERANCE.items():
        if config not in new:
            continue
        r, n = ref[config], new[config]
        metrics = {m: {"a1": round(r[m], 4), "a3": round(n[m], 4), "delta": round(n[m] - r[m], 4),
                       "within": abs(n[m] - r[m]) <= tol} for m in METRICS}
        out["configs"][config] = {
            "metrics": metrics, "match": all(v["within"] for v in metrics.values()),
            "latency_p50_ms": {"a1": round(r["latency_ms"]["total"]["p50_ms"], 1),
                               "a3": round(n["latency_ms"]["total"]["p50_ms"], 1)},
        }
    out["match"] = bool(out["configs"]) and all(c["match"] for c in out["configs"].values())
    return out


def render(res: dict) -> str:
    s = res["new_settings"]
    lines = ["# Tái lập A1 (M0)", "",
             f"Sinh tự động bởi `scripts/compare_a1.py` lúc {res['checked_at']}. So sánh run `{res['new_run']}` "
             f"với {res['reference_run']} trên chiến lược `{res['strategy']}`, {s.get('queries')} truy vấn, "
             f"qrels pooled. Reranker `{s.get('rerank_model')}`, pg_search {s.get('pg_search_version')}, "
             f"probe {s.get('vector_cluster_max_probe')}.", "",
             "| Cấu hình | Metric | A1 | A3 | Δ | Trong ngưỡng |", "|---|---|---:|---:|---:|---|"]
    for config, c in res["configs"].items():
        for m, v in c["metrics"].items():
            lines.append(f"| {config} | {m} | {v['a1']:.3f} | {v['a3']:.3f} | {v['delta']:+.3f} | "
                         f"{'có' if v['within'] else 'KHÔNG'} (±{res['tolerance'][config]}) |")
    lines += ["", "Độ trễ p50 end-to-end (chỉ ghi nhận, khác máy):", ""]
    lines += [f"- {config}: A1 {c['latency_p50_ms']['a1']} ms, A3 {c['latency_p50_ms']['a3']} ms"
              for config, c in res["configs"].items()]
    lines += ["", f"**Kết luận: {'khớp A1 trong ngưỡng' if res['match'] else 'CHƯA khớp, cần phân tích theo truy vấn'}.**", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", type=Path, help="the new run folder, e.g. eval/runs/20261012-101500")
    run = p.parse_args().run.resolve()
    res = compare(run)
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
