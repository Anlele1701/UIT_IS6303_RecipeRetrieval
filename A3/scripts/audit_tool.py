"""M2 blind labeling tool: Thy labels the 200 sampled Recipes for allergens and diet (docs/annotation_guide.md).

    uv run scripts/audit_tool.py      # then open http://localhost:8765

Blind by construction: reads only recipe, category, recipe_ingredient and eval/labels/allergen_sample.csv.
It never touches tags, the lexicon or checker output, and the API returns only the fields below.
Every save appends a row to eval/labels/allergen_gold.csv (the last row per Recipe wins), so labeling
can stop and resume at any time.
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from api import config  # noqa: E402

SAMPLE = ROOT / "eval" / "labels" / "allergen_sample.csv"
GOLD = ROOT / "eval" / "labels" / "allergen_gold.csv"
PAGE = Path(__file__).with_name("audit_tool.html")
ALLERGENS = ["milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanut", "wheat", "soy", "sesame"]
DIETS = ["vegetarian", "vegan"]
FIELDS = ["sample_order", "recipe_id", *ALLERGENS, *DIETS, "note", "labeled_at"]
RECIPE_FIELDS = {"order", "total", "recipe_id", "title", "category", "ingredients", "directions", "saved"}
Level = str  # "yes" | "maybe" | "no"


class Label(BaseModel):
    labels: dict[str, str] = Field(description="allergen or diet -> yes | maybe | no")
    note: str = ""


def sample() -> list[dict]:
    with open(SAMPLE, newline="", encoding="utf-8") as f:
        return sorted(csv.DictReader(f), key=lambda r: int(r["sample_order"]))


def saved() -> dict[int, dict]:
    """Latest saved row per Recipe."""
    if not GOLD.exists():
        return {}
    with open(GOLD, newline="", encoding="utf-8") as f:
        return {int(r["recipe_id"]): r for r in csv.DictReader(f)}


def recipe(conn, recipe_id: int) -> dict:
    row = conn.execute("SELECT r.title, c.name, r.directions FROM recipe r JOIN category c ON c.id = r.category_id "
                       "WHERE r.id = %s", [recipe_id]).fetchone()
    lines = [line for (line,) in conn.execute(
        "SELECT line FROM recipe_ingredient WHERE recipe_id = %s ORDER BY position", [recipe_id])]
    return {"title": row[0], "category": row[1], "directions": row[2], "ingredients": lines}


def create_app(database_url: str = config.DATABASE_URL) -> FastAPI:
    app = FastAPI(title="A3 blind allergen labeling")
    rows = sample()

    @app.get("/", response_class=HTMLResponse)
    def page():
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/state")
    def state():
        done = saved()
        first_open = next((int(r["sample_order"]) for r in rows if int(r["recipe_id"]) not in done), len(rows))
        return {"total": len(rows), "labeled": sum(1 for r in rows if int(r["recipe_id"]) in done),
                "next": first_open}

    @app.get("/api/recipe/{order}")
    def get_recipe(order: int):
        if not 1 <= order <= len(rows):
            raise HTTPException(404, "no such sample position")
        rid = int(rows[order - 1]["recipe_id"])
        with psycopg.connect(database_url) as conn:
            r = recipe(conn, rid)
        prev = saved().get(rid)
        out = {"order": order, "total": len(rows), "recipe_id": rid, **r,
               "saved": None if prev is None else {"labels": {k: prev[k] for k in ALLERGENS + DIETS},
                                                    "note": prev["note"]}}
        assert set(out) == RECIPE_FIELDS  # dev/holdout membership and any prediction stay out
        return out

    @app.post("/api/label/{order}")
    def label(order: int, body: Label):
        if not 1 <= order <= len(rows):
            raise HTTPException(404, "no such sample position")
        missing = [k for k in ALLERGENS + DIETS if body.labels.get(k) not in {"yes", "maybe", "no"}]
        if missing:
            raise HTTPException(422, f"choose yes, maybe or no for: {', '.join(missing)}")
        new = not GOLD.exists()
        with open(GOLD, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            if new:
                w.writeheader()
            w.writerow({"sample_order": order, "recipe_id": rows[order - 1]["recipe_id"],
                        **{k: body.labels[k] for k in ALLERGENS + DIETS}, "note": body.note.strip(),
                        "labeled_at": datetime.now().isoformat(timespec="seconds")})
        return state()

    return app


if __name__ == "__main__":
    print("Open http://localhost:8765  (Ctrl+C to stop; progress is saved after every Recipe)")
    uvicorn.run(create_app(), host="127.0.0.1", port=8765, log_level="warning")
