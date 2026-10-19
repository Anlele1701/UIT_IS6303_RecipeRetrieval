"""M6 human check (build plan M6.7): Thy labels three seeded samples, blind to the machine's answers.

    uv run scripts/eval_a3.py human-sample eval/runs/<ts>/a3    # writes the sample (display only) and the key
    uv run scripts/human_check.py                               # then open http://localhost:8767

Tasks:
  relevance  50 (query, Recipe) pairs from the judged pool: 0 / 1 / 2 by rubric 7.2 (constraints are not part of it)
  answer     50 answers with their context Recipes: faithful? answers the question (0/1/2)? cites a wrong dish?
  checker    60 checker verdicts (30 it called "yes", 30 "no"): does the Recipe contain the item?
The page shows the query, the Recipe text and the answer only: never the judge's score or the checker's verdict.
Those stay in the run folder (human_check_key.json); eval_a3.py score compares them with Thy's labels (Cohen's
kappa, checker accuracy). Every save appends a row to eval/labels/human_check.csv (the last row per item wins).
"""

import csv
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "eval" / "labels"
SAMPLE = LABELS / "human_check_sample.json"
OUT = LABELS / "human_check.csv"
PAGE = Path(__file__).with_name("human_check.html")
FIELDS = ["task", "item_id", "label", "note", "reviewer", "labeled_at"]
SEED = 42
N = {"relevance": 50, "answer": 50, "checker_yes": 30, "checker_no": 30}


def make_sample(run_dir: Path) -> str:
    """Draw the three samples from a scored run; display fields go to the page, answers to the run's key file."""
    run_dir = run_dir.resolve()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    import psycopg

    import adjudicate
    import checker
    from api import config
    rng = random.Random(SEED)
    pool = json.loads((run_dir / "pool.json").read_text(encoding="utf-8"))
    verdicts = json.loads((run_dir / "checker_verdicts.json").read_text(encoding="utf-8"))
    turns = [json.loads(line) for line in (run_dir / "turns.jsonl").read_text(encoding="utf-8").splitlines() if line]
    items, key = [], {}
    with psycopg.connect(config.DATABASE_URL) as conn:
        def recipe(rid):
            title = conn.execute("SELECT title FROM recipe WHERE id = %s", [rid]).fetchone()[0]
            return {"recipe_id": rid, "title": title, "ingredients": adjudicate.raw_lines(conn, rid)}

        by_score = {s: [p for p in pool if p["judge"] == s] for s in (0, 1, 2)}
        rel = []
        for s in (2, 1, 0):  # as even over the judge's scores as the pool allows (the page does not show them)
            rng.shuffle(by_score[s])
            rel += by_score[s][:N["relevance"] // 3 + (s == 2) * (N["relevance"] % 3)]
        for i, p in enumerate(rel, 1):
            items.append({"task": "relevance", "id": f"rel_{i:02d}", "query": p["query"], "recipe": recipe(p["recipe_id"])})
            key[f"rel_{i:02d}"] = p["judge"]

        answered = [t for t in turns if t["answer"] and t["recipe_ids"] and t["route"] in {"retrieve", "detail"}]
        rng.shuffle(answered)
        for i, t in enumerate(answered[:N["answer"]], 1):
            items.append({"task": "answer", "id": f"ans_{i:02d}", "query": t["text"], "answer": t["answer"],
                          "context": [recipe(r) for r in t["recipe_ids"][:5]]})
            key[f"ans_{i:02d}"] = {"qid": t["qid"], "preset": t["preset"], "turn": t["turn"]}

        for want, n in (("yes", N["checker_yes"]), ("no", N["checker_no"])):
            pick = [v for v in verdicts if v["contains"] == want]
            rng.shuffle(pick)
            for v in pick[:n]:
                iid = f"chk_{len([k for k in key if k.startswith('chk_')]) + 1:02d}"
                items.append({"task": "checker", "id": iid, "item": checker.describe(v["constraint"]),
                              "constraint": v["constraint"], "recipe": recipe(v["recipe_id"])})
                key[iid] = v["contains"]
    rng.shuffle(items)  # mixed order: the checker's yes and no are not in two blocks
    SAMPLE.write_text(json.dumps({"run": str(run_dir.relative_to(ROOT)), "seed": SEED, "items": items},
                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (run_dir / "human_check_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return f"{len(items)} items -> {SAMPLE.relative_to(ROOT)} (key in {run_dir.name}/human_check_key.json)"


def labels() -> dict[str, dict]:
    if not OUT.exists():
        return {}
    with open(OUT, newline="", encoding="utf-8") as f:
        return {r["item_id"]: r for r in csv.DictReader(f)}


def kappa(a: list, b: list) -> float | None:
    """Cohen's kappa of two label lists (unweighted)."""
    if not a or len(a) != len(b):
        return None
    cats = sorted(set(a) | set(b), key=str)
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else 1.0


def create_app():
    import uvicorn  # noqa: F401  (the server below)
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel

    app = FastAPI(title="A3 M6 human check")
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    rows = data["items"]

    class Label(BaseModel):
        label: dict
        note: str = ""

    @app.get("/", response_class=HTMLResponse)
    def page():
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/state")
    def state():
        done = labels()
        first = next((i + 1 for i, it in enumerate(rows) if it["id"] not in done), len(rows))
        return {"total": len(rows), "labeled": sum(it["id"] in done for it in rows), "next": first,
                "by_task": {t: sum(it["task"] == t for it in rows) for t in ("relevance", "answer", "checker")}}

    @app.get("/api/item/{order}")
    def item(order: int):
        if not 1 <= order <= len(rows):
            raise HTTPException(404, "no such item")
        prev = labels().get(rows[order - 1]["id"])
        return {"order": order, "total": len(rows), **rows[order - 1],
                "saved": None if prev is None else {"label": json.loads(prev["label"]), "note": prev["note"]}}

    @app.post("/api/label/{order}")
    def save(order: int, body: Label):
        if not 1 <= order <= len(rows):
            raise HTTPException(404, "no such item")
        it = rows[order - 1]
        need: dict[str, set] = {"relevance": {"score"}, "answer": {"faithful", "answers", "wrong_citation"},
                                "checker": {"contains"}}
        if set(body.label) != need[it["task"]]:
            raise HTTPException(422, f"fill: {', '.join(sorted(need[it['task']]))}")
        new = not OUT.exists()
        with open(OUT, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            if new:
                w.writeheader()
            w.writerow({"task": it["task"], "item_id": it["id"], "label": json.dumps(body.label, ensure_ascii=False),
                        "note": body.note.strip(), "reviewer": "Thy",
                        "labeled_at": datetime.now().isoformat(timespec="seconds")})
        return state()

    return app


def agreement(run_dir: Path, judged_faithful: dict[tuple, int | None]) -> dict:
    """Thy against the machine: kappa on relevance and faithfulness, checker accuracy (unsure counts as yes)."""
    key_path = run_dir / "human_check_key.json"
    if not key_path.exists() or not OUT.exists():
        return {}
    key = json.loads(key_path.read_text(encoding="utf-8"))
    lab = {i: json.loads(r["label"]) for i, r in labels().items()}
    rel = [(lab[i]["score"], key[i]) for i in key if i.startswith("rel_") and i in lab]
    fa = [(int(lab[i]["faithful"]), judged_faithful.get((key[i]["qid"], key[i]["preset"], key[i]["turn"])))
          for i in key if i.startswith("ans_") and i in lab]
    fa = [(a, b) for a, b in fa if b is not None]
    chk = [(lab[i]["contains"], key[i]) for i in key if i.startswith("chk_") and i in lab]
    to_bool = {"yes": True, "unsure": True, "error": True, "no": False}
    return {"relevance": {"n": len(rel), "kappa": kappa([a for a, _ in rel], [b for _, b in rel]),
                         "agree": round(sum(a == b for a, b in rel) / len(rel), 4) if rel else None},
            "faithfulness": {"n": len(fa), "kappa": kappa([a for a, _ in fa], [b for _, b in fa])},
            "checker": {"n": len(chk), "accuracy": round(sum(to_bool[a] == to_bool[b] for a, b in chk) / len(chk), 4)
                        if chk else None, "kappa": kappa([to_bool[a] for a, _ in chk], [to_bool[b] for _, b in chk])}}


if __name__ == "__main__":
    import uvicorn
    print("Open http://localhost:8767  (Ctrl+C to stop; progress is saved after every item)")
    uvicorn.run(create_app(), host="127.0.0.1", port=8767, log_level="warning")
