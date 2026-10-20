"""No-patient regression: what the chat pipeline decides for the demo scenarios, without a patient (MV3).

    uv run scripts/regression_snapshot.py --out eval/mv3_regression_baseline.json   # once, before MV3's changes
    uv run python -m pytest -q -m slow tests/test_no_patient_regression.py           # after: must match

Runs the four demo scenarios of tests/test_pipeline_demo.py (presets S and B0) on the live DB with the real M1,
embeddings and reranker. M6 is replaced by a fixed answer, so the history M1 reads on the next turn is the same
on every run (M1 stays a cache hit) and the comparison does not depend on generated text. Records, per turn,
the constraints event (intent, route, constraints, notices) and the Recipe ids in order.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx
import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import config  # noqa: E402
from api.pipeline import orchestrator as orch  # noqa: E402
from api.pipeline.flags import preset  # noqa: E402

FIXED_ANSWER = "Đây là vài gợi ý."
SCENARIOS = [  # (scenario, preset, turns in one session)
    ("1 allergy", "B0", ["Tôi dị ứng đậu phộng, gợi ý món gà xào sốt đậu phộng kiểu Thái"]),
    ("1 allergy", "S", ["Tôi dị ứng đậu phộng, gợi ý món gà xào sốt đậu phộng kiểu Thái"]),
    ("2 three turns", "S", ["gợi ý món gà cho bữa tối", "không dùng sữa nhé", "món thứ 2 làm thế nào?"]),
    ("3 no answer", "S", ["công thức bánh chưng thuần chay không gạo nếp, không đậu xanh"]),
    ("3 out of scope", "S", ["dự báo thời tiết Hà Nội ngày mai"]),
    ("4 lift", "S", ["I'm allergic to shellfish, suggest a quick pasta dinner",
                     "actually I can eat shellfish now, shrimp pasta please"]),
]


def snapshot(bot) -> list[dict]:
    out = []
    for scenario, name, turns in SCENARIOS:
        sid = bot.new_session(name)
        for msg in turns:
            ev = {}
            for e in bot.run_turn(sid, msg, preset(name)):
                if e.type in {"constraints", "recipes"}:
                    ev[e.type] = e.data
            c = ev["constraints"]
            out.append({"scenario": scenario, "preset": name, "message": msg, "intent": c["intent"],
                        "route": c["route"], "constraints": c["constraints"], "notices": c["notices"],
                        "recipe_ids": [r["id"] for r in ev.get("recipes", [])]})
    return out


def run() -> list[dict]:
    from api.rerank import Reranker
    real = orch.m6.generate
    orch.m6.generate = lambda client, messages, usage=None, **kw: iter([FIXED_ANSWER])  # see the module docstring
    try:
        with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=900) as client:
            return snapshot(orch.Assistant(conn, client, Reranker().score))
    finally:
        orch.m6.generate = real


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    rows = run()
    Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in rows:
        print(f"{r['scenario']:<15} {r['preset']:<3} {r['route']:<9} {r['recipe_ids']}")


if __name__ == "__main__":
    main()
