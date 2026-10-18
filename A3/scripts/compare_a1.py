"""M0 reproduction check: new Evaluation runs against A1's reference runs (eval/a1_reference).

    uv run scripts/compare_a1.py eval/runs/<served>                       # served settings (probe 0.02)
    uv run scripts/compare_a1.py eval/runs/<served> --exact eval/runs/<exact>
        # <exact>: `PGOPTIONS="-c paradedb.vector_cluster_max_probe=1.0" uv run scripts/evaluate.py --configs dense fusion`

Writes eval/m0_reproduction.json and docs/m0_reproduction.md; nothing is typed by hand.
Quality metrics are judged against a tolerance; latency is recorded only, since the machine differs.
The exact check compares against A1's exact-dense Ablation run: with the ANN index out of the way the
numbers must be identical, which separates "same data, embeddings and code" from IVF clustering noise.
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
EXACT_TOLERANCE = {"dense": 0.0005, "fusion": 0.0005}  # rounding only: exact search must reproduce A1
STRATEGY = "semantic"


def rows(run: Path, variant: str = "default") -> dict[str, dict]:
    return {m["config"]: m for m in json.loads((run / "metrics.json").read_text(encoding="utf-8"))
            if m["strategy"] == STRATEGY and m.get("variant", "default") == variant}


def rel(run: Path) -> str:
    return (run.relative_to(ROOT) if run.is_relative_to(ROOT) else run).as_posix()


def section(ref: dict, new: dict, tolerance: dict) -> dict:
    out = {}
    for config, tol in tolerance.items():
        if config not in new:
            continue
        r, n = ref[config], new[config]
        metrics = {m: {"a1": round(r[m], 4), "a3": round(n[m], 4), "delta": round(n[m] - r[m], 4),
                       "within": abs(n[m] - r[m]) <= tol} for m in METRICS}
        out[config] = {"metrics": metrics, "match": all(v["within"] for v in metrics.values()),
                       "latency_p50_ms": {"a1": round(r["latency_ms"]["total"]["p50_ms"], 1),
                                          "a3": round(n["latency_ms"]["total"]["p50_ms"], 1)}}
    return out


def compare(run: Path, exact: Path | None = None) -> dict:
    out = {"checked_at": datetime.now().isoformat(timespec="seconds"), "strategy": STRATEGY,
           "reference_run": "A1 eval/pooled/20261006-224100", "new_run": rel(run),
           "reference_settings": json.loads((REFERENCE / "settings.json").read_text(encoding="utf-8")),
           "new_settings": json.loads((run / "settings.json").read_text(encoding="utf-8")),
           "tolerance": TOLERANCE, "configs": section(rows(REFERENCE), rows(run), TOLERANCE)}
    out["match"] = bool(out["configs"]) and all(c["match"] for c in out["configs"].values())
    if exact:
        ref = REFERENCE / "exact-dense"
        out["exact"] = {"reference_run": "A1 eval/pooled/20260929-195231 (arm exact-dense, probe 1.0)",
                        "new_run": rel(exact),
                        "new_probe": json.loads((exact / "settings.json").read_text(encoding="utf-8"))
                        .get("vector_cluster_max_probe"),
                        "tolerance": EXACT_TOLERANCE,
                        "configs": section(rows(ref, "arm"), rows(exact), EXACT_TOLERANCE)}
        out["exact"]["match"] = bool(out["exact"]["configs"]) and all(
            c["match"] for c in out["exact"]["configs"].values())
    return out


def table(configs: dict, tolerance: dict) -> list[str]:
    lines = ["| Cấu hình | Metric | A1 | A3 | Δ | Trong ngưỡng |", "|---|---|---:|---:|---:|---|"]
    for config, c in configs.items():
        for m, v in c["metrics"].items():
            lines.append(f"| {config} | {m} | {v['a1']:.3f} | {v['a3']:.3f} | {v['delta']:+.3f} | "
                         f"{'có' if v['within'] else 'KHÔNG'} (±{tolerance[config]}) |")
    return lines


def render(res: dict) -> str:
    s = res["new_settings"]
    lines = ["# Tái lập A1 (M0)", "",
             f"Sinh tự động bởi `scripts/compare_a1.py` lúc {res['checked_at']}. Chiến lược `{res['strategy']}`, "
             f"{s.get('queries')} truy vấn, qrels pooled, reranker `{s.get('rerank_model')}`, "
             f"pg_search {s.get('pg_search_version')}.", "",
             f"## 1. Cấu hình phục vụ (probe {s.get('vector_cluster_max_probe')})", "",
             f"Run `{res['new_run']}` so với {res['reference_run']}.", ""]
    lines += table(res["configs"], res["tolerance"])
    lines += ["", f"Kết luận: {'khớp trong ngưỡng' if res['match'] else 'có metric vượt ngưỡng'}.", ""]
    if "exact" in res:
        e = res["exact"]
        lines += [f"## 2. Dense chính xác (probe {e['new_probe']}), loại bỏ ảnh hưởng của index ANN", "",
                  f"Run `{e['new_run']}` so với {e['reference_run']}.", ""]
        lines += table(e["configs"], e["tolerance"])
        lines += ["", f"Kết luận: {'trùng A1' if e['match'] else 'KHÁC A1'}.", ""]
    lines += ["## Độ trễ p50 end-to-end (chỉ ghi nhận, khác máy)", ""]
    lines += [f"- {config}: A1 {c['latency_p50_ms']['a1']} ms, A3 {c['latency_p50_ms']['a3']} ms"
              for config, c in res["configs"].items()]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", type=Path, help="the served-settings run folder, e.g. eval/runs/20261012-002242")
    p.add_argument("--exact", type=Path, help="a dense/fusion run at probe 1.0")
    a = p.parse_args()
    res = compare(a.run.resolve(), a.exact.resolve() if a.exact else None)
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
