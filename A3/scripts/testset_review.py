"""M5 V6: Thy confirms (or fixes, or drops) the gold intent and constraints of every test set candidate.

    uv run scripts/testset_review.py      # then open http://localhost:8766

Blind by construction: reads only eval/testset/candidates/*.jsonl (the query text and the gold written from its
template, or none for a handwritten query) and the review file. It shows no M1 prediction, no tag and no checker
verdict, and imports nothing from the pipeline, the tagger or the checker (tests/test_testset_review.py).
Every save appends a row to eval/labels/testset_review.csv (the last row per item wins, reviewer Thy), so the
review can stop and resume at any time. scripts/freeze_testset.py applies it.

Draft mode (Thy chose it, 19/10/2026): if eval/labels/testset_review_draft.csv exists (scripts/draft_testset_review.py,
reviewer claude-draft), each item shows that draft as its proposal and whether it is flagged; "Đúng" then accepts the
draft gold. "Chấp nhận các câu không bị đánh dấu" lets Thy accept, in one click she confirms, every unreviewed item
the draft keeps as written and does not flag; those rows say so in their note and are counted apart at the freeze.
The draft is a model's proposal, so the page labels it as such.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "eval" / "testset" / "candidates"
REVIEW = ROOT / "eval" / "labels" / "testset_review.csv"
DRAFT = ROOT / "eval" / "labels" / "testset_review_draft.csv"
BULK_NOTE = "bulk-accepted: unflagged, gold as its template wrote it"
PAGE = Path(__file__).with_name("testset_review.html")
SETS = ["t1", "t2", "t3", "t4"]
FIELDS = ["item_id", "decision", "gold", "note", "reviewer", "reviewed_at"]
ITEM_FIELDS = {"order", "total", "id", "set", "lang", "source", "kind", "text", "turns", "gold", "needs_gold", "note",
               "saved", "draft"}


def items() -> list[dict]:
    out = []
    for s in SETS:
        path = CAND / f"{s}.jsonl"
        if path.exists():
            out += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out


def saved() -> dict[str, dict]:
    if not REVIEW.exists():
        return {}
    with open(REVIEW, newline="", encoding="utf-8") as f:
        return {r["item_id"]: r for r in csv.DictReader(f)}


def drafts() -> dict[str, dict]:
    if not DRAFT.exists():
        return {}
    with open(DRAFT, newline="", encoding="utf-8") as f:
        return {r["item_id"]: r for r in csv.DictReader(f)}


def draft_view(d: dict | None) -> dict | None:
    if d is None:
        return None
    return {"decision": d["decision"], "gold": json.loads(d["gold"]) if d["gold"] else None, "note": d["note"],
            "flagged": d["flagged"] == "True", "flag_reason": d["flag_reason"]}


def view(it: dict, order: int, total: int, prev: dict | None, draft: dict | None = None) -> dict:
    """What the page may see: the query, its proposed gold and the draft (labelled as a model's); never M1's
    prediction, a tag or a checker verdict."""
    out = {"order": order, "total": total, "id": it["id"], "set": it["set"], "lang": it["lang"],
           "source": it.get("source", ""), "kind": it.get("kind", ""), "text": it["text"],
           "turns": [{"text": t["text"], "gold": t.get("gold")} for t in it.get("turns", [])] or None,
           "gold": it.get("gold") if "turns" not in it else None, "needs_gold": bool(it.get("needs_gold")),
           "note": it.get("note", ""),
           "saved": None if prev is None else {"decision": prev["decision"], "gold": json.loads(prev["gold"] or "null"),
                                               "note": prev["note"]},
           "draft": draft_view(draft)}
    assert set(out) == ITEM_FIELDS
    return out


class Review(BaseModel):
    decision: Literal["ok", "edit", "drop"]
    gold: dict | list | None = Field(default=None, description="the corrected gold (a list of per-turn golds for T4)")
    note: str = ""


def valid_gold(g: dict) -> bool:
    c = g.get("constraints") or {}
    return (g.get("intent") in {"search", "refine", "ask_detail", "out_of_scope", "chitchat"}
            and isinstance(c.get("allergens_exclude", []), list) and isinstance(c.get("ingredients_exclude", []), list)
            and c.get("diet") in {None, "vegetarian", "vegan"}
            and (c.get("max_total_minutes") is None or isinstance(c.get("max_total_minutes"), int)))


def create_app() -> FastAPI:
    app = FastAPI(title="A3 test set gold review (V6)")
    rows = items()

    @app.get("/", response_class=HTMLResponse)
    def page():
        return PAGE.read_text(encoding="utf-8")

    def flagged(it, dr) -> bool:
        d = dr.get(it["id"])
        return d is None or d["flagged"] == "True"  # no draft: everything needs a look

    @app.get("/api/state")
    def state():
        done, dr = saved(), drafts()
        first_open = next((i + 1 for i, it in enumerate(rows) if it["id"] not in done), len(rows))
        first_flag = next((i + 1 for i, it in enumerate(rows) if it["id"] not in done and flagged(it, dr)), None)
        unflagged_open = sum(1 for it in rows if it["id"] not in done and not flagged(it, dr)
                             and dr[it["id"]]["decision"] == "ok")
        return {"total": len(rows), "reviewed": sum(1 for it in rows if it["id"] in done), "next": first_open,
                "next_flagged": first_flag, "flagged_open": sum(1 for it in rows if it["id"] not in done and flagged(it, dr)),
                "unflagged_open": unflagged_open, "has_draft": bool(dr),
                "by_set": {s: sum(1 for it in rows if it["set"] == s) for s in SETS}}

    @app.get("/api/next")
    def next_item(after: int = 0, only_flagged: bool = False):
        """The next unreviewed item after `after` (wrapping), flagged ones only if asked."""
        done, dr = saved(), drafts()
        order = list(range(after, len(rows))) + list(range(0, after))
        for i in order:
            it = rows[i]
            if it["id"] not in done and (not only_flagged or flagged(it, dr)):
                return {"order": i + 1}
        return {"order": None}

    class Bulk(BaseModel):
        confirm: bool

    @app.post("/api/bulk_accept")
    def bulk_accept(body: Bulk):
        """Thy accepts every unreviewed, unflagged item whose draft keeps the template's gold."""
        if body.confirm is not True:
            raise HTTPException(422, "confirm=true is required")
        done, dr = saved(), drafts()
        todo = [it for it in rows if it["id"] not in done and not flagged(it, dr) and dr[it["id"]]["decision"] == "ok"]
        now = datetime.now().isoformat(timespec="seconds")
        new = not REVIEW.exists()
        with open(REVIEW, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            if new:
                w.writeheader()
            for it in todo:
                w.writerow({"item_id": it["id"], "decision": "ok", "gold": "", "note": BULK_NOTE, "reviewer": "Thy",
                            "reviewed_at": now})
        return {**state(), "accepted": len(todo)}

    @app.get("/api/item/{order}")
    def get_item(order: int):
        if not 1 <= order <= len(rows):
            raise HTTPException(404, "no such item")
        it = rows[order - 1]
        return view(it, order, len(rows), saved().get(it["id"]), drafts().get(it["id"]))

    @app.post("/api/review/{order}")
    def review(order: int, body: Review):
        if not 1 <= order <= len(rows):
            raise HTTPException(404, "no such item")
        it = rows[order - 1]
        gold = body.gold
        if body.decision == "ok":
            d = drafts().get(it["id"])
            if d and d["gold"]:  # accepting the draft: its gold is what Thy confirms
                gold = json.loads(d["gold"])
            else:
                missing = it.get("needs_gold") or ("turns" in it and any(t.get("gold") is None for t in it["turns"]))
                if missing:
                    raise HTTPException(422, "this query has no gold yet: choose Sửa and fill it")
                gold = None  # keep the proposed gold
        elif body.decision == "edit":
            golds = gold if isinstance(gold, list) else [gold]
            if not golds or not all(isinstance(g, dict) and valid_gold(g) for g in golds):
                raise HTTPException(422, "the gold needs an intent and constraints in M1's schema")
        new = not REVIEW.exists()
        REVIEW.parent.mkdir(parents=True, exist_ok=True)
        with open(REVIEW, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            if new:
                w.writeheader()
            w.writerow({"item_id": it["id"], "decision": body.decision,
                        "gold": json.dumps(gold, ensure_ascii=False) if gold is not None else "",
                        "note": body.note.strip(), "reviewer": "Thy",
                        "reviewed_at": datetime.now().isoformat(timespec="seconds")})
        return state()

    return app


if __name__ == "__main__":
    print("Open http://localhost:8766  (Ctrl+C to stop; progress is saved after every item)")
    uvicorn.run(create_app(), host="127.0.0.1", port=8766, log_level="warning")
