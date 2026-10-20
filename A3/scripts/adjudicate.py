"""Adjudication of the independent checker's "yes" verdicts (Thy, after MV3; docs/annotation_guide.md section 8).

    uv run scripts/adjudicate.py queue --pairs <file.json>   # write the blind review queue eval/labels/checker_queue.csv

A "yes" (the Recipe contains the constraint) is scored in two ways, the same for every preset, B0 and B1 included:
- CVR_raw counts every "yes" (strict, an upper bound).
- CVR_adjudicated drops a "yes" whose evidence the checker itself marked invalid, or whose evidence is not found
  verbatim (case-insensitive) in one of the Recipe's raw ingredient lines (automatic step). A "yes" that passes
  that step may still be wrong in meaning ("salmon" as evidence of wheat): it goes to a human queue and counts
  as a violation until a reviewer labels it in eval/labels/checker_adjudication.csv (pending = violation).
The queue shows the Recipe, the constraint and the evidence only: never which preset or run returned the Recipe.
Like scripts/checker.py this reads only recipe and recipe_ingredient, with its own SQL, and imports nothing from
the tagger (tests/test_checker_independence.py).
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "eval" / "labels" / "checker_adjudication.csv"
QUEUE = ROOT / "eval" / "labels" / "checker_queue.csv"
LABEL_COLUMNS = ["recipe_id", "constraint", "evidence_line", "violation", "reviewer", "date", "note"]


@dataclass(frozen=True)
class Scored:
    recipe_id: int
    constraint: str
    verdict: str  # yes | no | unsure | error (the checker's)
    evidence_line: str
    status: str  # not_yes | dropped_flagged | dropped_not_verbatim | confirmed | rejected | pending
    raw: bool  # counts in CVR_raw
    adjudicated: bool  # counts in CVR_adjudicated (pending counts)


def raw_lines(conn, recipe_id: int) -> list[str]:
    return [line for (line,) in conn.execute("SELECT line FROM recipe_ingredient WHERE recipe_id = %s ORDER BY position",
                                             [recipe_id])]


def verbatim(evidence: str, lines: list[str]) -> bool:
    """The evidence occurs as written (case-insensitive; runs of spaces count as one) in one raw line."""
    ev = " ".join(evidence.lower().split())
    return bool(ev) and any(ev in " ".join(line.lower().split()) for line in lines)


def load_labels(path: Path = LABELS) -> dict[tuple[int, str], dict]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["violation"] not in {"yes", "no"}:
            raise ValueError(f"{path.name}: violation must be yes or no: {r}")
    return {(int(r["recipe_id"]), r["constraint"]): r for r in rows}


def score(recipe_id: int, constraint: str, verdict, lines: list[str], labels: dict) -> Scored:
    """One checker verdict (scripts/checker.Verdict) -> how it counts in CVR_raw and CVR_adjudicated."""
    ev = verdict.evidence_line or ""
    if verdict.contains != "yes":
        return Scored(recipe_id, constraint, verdict.contains, ev, "not_yes", False, False)
    if not verdict.evidence_ok:
        return Scored(recipe_id, constraint, "yes", ev, "dropped_flagged", True, False)
    if not verbatim(ev, lines):
        return Scored(recipe_id, constraint, "yes", ev, "dropped_not_verbatim", True, False)
    label = labels.get((recipe_id, constraint))
    if label is None:
        return Scored(recipe_id, constraint, "yes", ev, "pending", True, True)
    yes = label["violation"] == "yes"
    return Scored(recipe_id, constraint, "yes", ev, "confirmed" if yes else "rejected", True, yes)


def score_all(conn, verdicts: dict[tuple[int, str], object], labels: dict | None = None) -> list[Scored]:
    labels = load_labels() if labels is None else labels
    lines: dict[int, list[str]] = {}
    out = []
    for (rid, c), v in sorted(verdicts.items()):
        if rid not in lines:
            lines[rid] = raw_lines(conn, rid)
        out.append(score(rid, c, v, lines[rid], labels))
    return out


def write_queue(conn, scored: list[Scored], path: Path = QUEUE) -> int:
    """Pending items, blind: Recipe, constraint, evidence and its raw lines; no preset, no run, no tag."""
    pending = [s for s in scored if s.status == "pending"]
    known = set()
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            known = {(int(r["recipe_id"]), r["constraint"]) for r in csv.DictReader(f)}
    new = [s for s in pending if (s.recipe_id, s.constraint) not in known]
    first = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if first:
            w.writerow(["recipe_id", "title", "constraint", "evidence_line", "ingredient_lines"])
        for s in new:
            title = conn.execute("SELECT title FROM recipe WHERE id = %s", [s.recipe_id]).fetchone()[0]
            w.writerow([s.recipe_id, title, s.constraint, s.evidence_line, " | ".join(raw_lines(conn, s.recipe_id))])
    return len(new)


def summary(scored: list[Scored], recipes: int) -> dict:
    """Violating Recipes under each count (a Recipe breaking two constraints counts once)."""
    raw = {s.recipe_id for s in scored if s.raw}
    adj = {s.recipe_id for s in scored if s.adjudicated}
    return {"recipes": recipes, "violating_raw": len(raw), "violating_adjudicated": len(adj),
            "cvr_raw": round(len(raw) / recipes, 4) if recipes else None,
            "cvr_adjudicated": round(len(adj) / recipes, 4) if recipes else None,
            "pending": sum(s.status == "pending" for s in scored),
            "by_status": {k: sum(s.status == k for s in scored) for k in
                          ("dropped_flagged", "dropped_not_verbatim", "confirmed", "rejected", "pending")}}


def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    import checker
    import psycopg

    from api import config  # noqa: F401  (DATABASE_URL)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue")
    q.add_argument("--pairs", required=True, help='JSON list of [recipe_id, "allergen:<code>"] pairs')
    args = ap.parse_args()
    pairs = [(int(r), c) for r, c in json.loads(Path(args.pairs).read_text(encoding="utf-8"))]
    cache = checker.load_cache()
    with psycopg.connect(config.DATABASE_URL) as conn:
        verdicts = {}
        for rid, c in pairs:
            verdicts.update({(rid, k): v for k, v in checker.check(conn, None, rid, [c], cache).items()})
        n = write_queue(conn, score_all(conn, verdicts))
    print(f"{n} new items in {QUEUE.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
