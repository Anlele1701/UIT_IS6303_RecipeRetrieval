"""The checker's blind review queue as a spreadsheet (Thy, M6c): label offline, then import.

    uv run scripts/adjudication_sheet.py export            # pending queue rows -> eval/labels/checker_adjudication_sheet.csv
    uv run scripts/adjudication_sheet.py import [sheet]    # filled rows -> appended to eval/labels/checker_adjudication.csv

The sheet shows what the queue shows (Recipe, constraint, evidence, ingredient lines) plus the group note of the
human check page: never which preset or run returned the Recipe. Rows already in checker_adjudication.csv are not
exported and never overwritten; one wrong row blocks the whole import.
"""

import csv
import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adjudicate  # noqa: E402
from human_check import GROUP_VI  # noqa: E402

SHEET = adjudicate.ROOT / "eval" / "labels" / "checker_adjudication_sheet.csv"
SHEET_FIELDS = ["order", "recipe_id", "title", "constraint", "group_note", "evidence_line", "ingredient_lines",
                "violation", "note"]
VIOLATION = {"yes": "yes", "co": "yes", "có": "yes", "1": "yes", "no": "no", "khong": "no", "không": "no", "0": "no"}


def pending(queue: Path = adjudicate.QUEUE, labels: Path = adjudicate.LABELS) -> list[dict]:
    done = adjudicate.load_labels(labels)
    with open(queue, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if (int(r["recipe_id"]), r["constraint"]) not in done]


def export_sheet(path: Path = SHEET, queue: Path = adjudicate.QUEUE, labels: Path = adjudicate.LABELS) -> str:
    rows = pending(queue, labels)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_FIELDS)
        w.writeheader()
        for n, r in enumerate(rows, 1):
            grp = r["constraint"].split(":", 1)[1]
            w.writerow({"order": n, "recipe_id": r["recipe_id"], "title": r["title"], "constraint": r["constraint"],
                        "group_note": GROUP_VI.get(grp, grp), "evidence_line": r["evidence_line"],
                        "ingredient_lines": "\n".join(x.strip() for x in r["ingredient_lines"].split(" | ")),
                        "violation": "", "note": ""})
    return f"{len(rows)} pending rows -> {path}"


def import_sheet(path: Path = SHEET, labels: Path = adjudicate.LABELS) -> str:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:  # Excel "CSV" (not "CSV UTF-8") on a Vietnamese Windows
        text = raw.decode("cp1258")
    first = text.split("\n", 1)[0]
    sheet = list(csv.DictReader(io.StringIO(text, newline=""), delimiter=";" if first.count(";") > first.count(",") else ","))
    done = adjudicate.load_labels(labels)
    new, errors, blank, kept = [], [], 0, 0
    for r in sheet:
        v = (r.get("violation") or "").strip().lower()
        if not v:
            blank += 1
            continue
        k = (int(r["recipe_id"]), r["constraint"])
        if k in done:
            kept += 1
            continue
        if v not in VIOLATION:
            errors.append(f"order {r.get('order')}: violation = {v!r} (yes/no)")
            continue
        new.append({"recipe_id": r["recipe_id"], "constraint": r["constraint"], "evidence_line": r["evidence_line"],
                    "violation": VIOLATION[v], "reviewer": "Thy", "date": f"{date.today():%m/%d/%Y}",
                    "note": (r.get("note") or "").strip()})
    if errors:
        return "not imported, fix these rows:\n  " + "\n  ".join(errors)
    with open(labels, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=adjudicate.LABEL_COLUMNS, lineterminator="\n").writerows(new)
    return f"imported {len(new)}, blank {blank}, already labeled kept {kept}; still pending {len(pending(labels=labels))}"


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = Path(sys.argv[2]) if len(sys.argv) > 2 else SHEET
    if cmd == "export":
        print(export_sheet(arg))
    elif cmd == "import":
        print(import_sheet(arg))
    else:
        sys.exit(__doc__)
