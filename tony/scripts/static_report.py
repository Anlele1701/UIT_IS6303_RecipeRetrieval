"""Write report.html: the evaluation results as one self-contained file that opens in any browser.

    uv run python scripts/static_report.py            # reads ui/public/report.json, writes report.html

It embeds only what the page draws from the report bundle (metrics, significance, ablations, failure counts,
answer-key and query-set summaries), so it needs no database, Ollama, API or npm. Rebuild it after
report_bundle.py; a test fails when it is older than the bundle.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "ui" / "public" / "report.json"
OUT = ROOT / "report.html"
TEMPLATE = Path(__file__).resolve().parent / "static_report.html"

KEEP = ["metrics", "significance", "ablations", "qrels", "query_set", "headline", "rerank"]


def page_data(bundle: dict) -> dict:
    manifest = bundle["meta"]["manifest"]
    report_run = bundle["meta"]["runs"][manifest["report_run"]]
    failures = {k: bundle["failures"][k] for k in ("counts", "group_sizes", "overlap")}
    corpus = {"recipes": bundle["corpus"]["recipes"], "categories": bundle["corpus"]["categories"],
              "strategies": {name: {"parameters": s["parameters"], "chunks": s["chunks"]}
                             for name, s in bundle["corpus"]["strategies"].items()}}
    return {"run": {"name": manifest["report_run"], **report_run}, "timing_repeats": manifest["timing_repeats"],
            "built_at": bundle["meta"]["built_at"], "alpha": bundle["meta"]["alpha"],
            "failures": failures, "corpus": corpus, **{k: bundle[k] for k in KEEP}}


def render(bundle: dict) -> str:
    data = json.dumps(page_data(bundle), separators=(",", ":")).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", data)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bundle", type=Path, default=BUNDLE)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    a.out.write_text(render(json.loads(a.bundle.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"wrote {a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out}")


if __name__ == "__main__":
    main()
