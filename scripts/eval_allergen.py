"""M2 step 5: precision/recall of the tagger and the independent checker against the sample labels.

    uv run scripts/eval_allergen.py [--iteration N]   # -> eval/labels/report_allergen.{json,md}

Labels are SILVER (eval/labels/allergen_gold.provenance.json): say so wherever the numbers are used.
Positive class = the Recipe contains the allergen; for diets, the Recipe breaks it (is not vegetarian/vegan).
Variants reported:
  label    yes only, or yes + maybe ("Có thể")
  tagger   definite tags only (the hard filter), or definite + possible (allergens_may / diet_may)
  checker  strict (unsure counts as contains) or lenient (unsure counts as not)
Precision and recall carry Wilson 95% intervals. Errors are listed for the dev split only: the holdout
is reported as numbers, never inspected while tuning the lexicon (iteration counts each tuning round).
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402

from api import config  # noqa: E402
from stats import rate  # noqa: E402

LABELS = ROOT / "eval" / "labels"
ALLERGENS = ["milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanut", "wheat", "soy", "sesame"]
DIETS = ["vegetarian", "vegan"]
GROUPS = ALLERGENS + DIETS
SPLITS = ["dev", "holdout", "all"]
MAX_ERRORS = 15


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- positive/negative per source -------------------------------------------------------------

def label_pos(row: dict, group: str, with_maybe: bool) -> bool:
    if group in DIETS:  # the label says whether the Recipe IS vegetarian/vegan; positive = breaks it
        return row[group] == "no" or (with_maybe and row[group] == "maybe")
    return row[group] == "yes" or (with_maybe and row[group] == "maybe")


def tagger_pos(tag: dict, group: str, with_possible: bool) -> bool:
    if group in DIETS:
        return group not in tag["diet_flags"] or (with_possible and group in tag["diet_may"])
    return group in tag["allergens"] or (with_possible and group in tag["allergens_may"])


def checker_pos(verdict: str, strict: bool) -> bool:
    return verdict == "yes" or (strict and verdict == "unsure")


def confusion(pairs: list[tuple[bool, bool]]) -> dict:
    tp = sum(1 for y, p in pairs if y and p)
    fp = sum(1 for y, p in pairs if not y and p)
    fn = sum(1 for y, p in pairs if y and not p)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": len(pairs) - tp - fp - fn,
            "precision": rate(tp, tp + fp), "recall": rate(tp, tp + fn)}


def compute(sample: list[dict], labels: dict[int, dict], tags: dict[int, dict],
            verdicts: dict[tuple[int, str], str]) -> dict:
    """All tables; pure, so tests can feed hand-made data."""
    split_of = {int(r["recipe_id"]): r["split"] for r in sample}
    ids = [rid for rid in split_of if rid in labels]
    systems = {
        "tagger_definite": lambda rid, g: tagger_pos(tags[rid], g, False),
        "tagger_with_possible": lambda rid, g: tagger_pos(tags[rid], g, True),
        "checker_strict": lambda rid, g: checker_pos(verdicts.get((rid, key(g)), "unsure"), True),
        "checker_lenient": lambda rid, g: checker_pos(verdicts.get((rid, key(g)), "unsure"), False),
    }
    out = {"recipes": {s: sum(1 for r in ids if s == "all" or split_of[r] == s) for s in SPLITS},
           "positives": {}, "pr": {}, "disagreement": {}}
    for with_maybe, lname in ((False, "label_yes"), (True, "label_yes_or_maybe")):
        out["pr"][lname] = {}
        for split in SPLITS:
            rows = [r for r in ids if split == "all" or split_of[r] == split]
            out["pr"][lname][split] = {
                sysname: {g: confusion([(label_pos(labels[r], g, with_maybe), pred(r, g)) for r in rows]) for g in GROUPS}
                for sysname, pred in systems.items()}
        out["positives"][lname] = {g: sum(label_pos(labels[r], g, with_maybe) for r in ids) for g in GROUPS}
    for g in GROUPS:  # tagger (hard filter) vs checker (strict), all labeled Recipes
        cells = {"both": 0, "tagger_only": 0, "checker_only": 0, "neither": 0}
        for r in ids:
            t, c = systems["tagger_definite"](r, g), systems["checker_strict"](r, g)
            cells["both" if t and c else "tagger_only" if t else "checker_only" if c else "neither"] += 1
        out["disagreement"][g] = cells
    return out


def key(group: str) -> str:
    return f"diet:{group}" if group in DIETS else f"allergen:{group}"


def errors(sample, labels, tags, verdicts, lines) -> dict:
    """Tagger and checker misses/false alarms on the dev split (label yes; definite tags; strict checker)."""
    out = {}
    for g in GROUPS:
        found = {"tagger_fn": [], "tagger_fp": [], "checker_fn": [], "checker_fp": []}
        for r in (int(s["recipe_id"]) for s in sample if s["split"] == "dev"):
            if r not in labels:
                continue
            y = label_pos(labels[r], g, False)
            for name, p in (("tagger", tagger_pos(tags[r], g, False)),
                            ("checker", checker_pos(verdicts.get((r, key(g)), "unsure"), True))):
                if y != p:
                    found[f"{name}_{'fn' if y else 'fp'}"].append(r)
        out[g] = {k: v[:MAX_ERRORS] for k, v in found.items()}
        out[g]["counts"] = {k: len(v) for k, v in found.items()}
    return out


# --- I/O --------------------------------------------------------------------------------------

def load(conn) -> tuple:
    sample = read_csv(LABELS / "allergen_sample.csv")
    labels = {int(r["recipe_id"]): r for r in read_csv(LABELS / "allergen_gold.csv")}  # last row per Recipe wins
    ids = [int(r["recipe_id"]) for r in sample]
    tags = {rid: {"allergens": a, "allergens_may": am, "diet_flags": d, "diet_may": dm} for rid, a, am, d, dm in conn.execute(
        "SELECT recipe_id, allergens, allergens_may, diet_flags, diet_may FROM recipe_tag WHERE recipe_id = ANY(%s)", [ids])}
    verdicts = {(int(r["recipe_id"]), r["constraint"]): r["contains"] for r in read_csv(LABELS / "checker_sample.csv")}
    evidence = [r for r in read_csv(LABELS / "checker_sample.csv")]
    lines = {}
    for rid, title, line in conn.execute(
            "SELECT r.id, r.title, i.line FROM recipe r JOIN recipe_ingredient i ON i.recipe_id = r.id "
            "WHERE r.id = ANY(%s) ORDER BY r.id, i.position", [ids]):
        lines.setdefault(rid, {"title": title, "lines": []})["lines"].append(line)
    return sample, labels, tags, verdicts, evidence, lines


def fmt(r: dict) -> str:
    if r["value"] is None:
        return "–"
    return f"{r['value']:.2f} [{r['ci95'][0]:.2f}–{r['ci95'][1]:.2f}]".replace(".", ",")


def render(res: dict) -> str:
    vi = {"milk": "Sữa", "egg": "Trứng", "fish": "Cá", "crustacean_shellfish": "Giáp xác", "tree_nuts": "Hạt cây",
          "peanut": "Đậu phộng", "wheat": "Lúa mì", "soy": "Đậu nành", "sesame": "Mè",
          "vegetarian": "Không chay (vegetarian)", "vegan": "Không thuần chay (vegan)"}
    out = ["# Báo cáo P/R của bộ gắn thẻ và bộ kiểm (M2)", "",
           f"Sinh tự động bởi `scripts/eval_allergen.py` lúc {res['ran_at']} · lần lặp {res['iteration']} · "
           f"commit `{res['git_commit']}`.", "",
           f"> **Nhãn là nhãn BẠC** ({res['provenance']['labeled_by']}; gán mù). Không có nhãn vàng do người gán. "
           "Bộ gắn thẻ do Claude Opus viết quy tắc, cùng họ với người gán nhãn, nên P/R của bộ gắn thẻ có thể bị "
           "thổi phồng. Bộ kiểm `llama3.1:8b` khác họ.", "",
           f"Số công thức: dev {res['recipes']['dev']}, holdout {res['recipes']['holdout']}, tổng {res['recipes']['all']}. "
           f"Bằng chứng của bộ kiểm hợp lệ: {fmt(res['checker_evidence_ok'])}.", ""]
    for lname, title in (("label_yes", "Nhãn dương = \"Có\""), ("label_yes_or_maybe", "Nhãn dương = \"Có\" hoặc \"Có thể\"")):
        for split in ("holdout", "all"):
            t = res["pr"][lname][split]
            out += [f"## {title} · tập {split}", "",
                    "| Nhóm | Số dương | Thẻ chắc chắn: P | R | Thẻ + có thể: P | R | Bộ kiểm strict: P | R | Bộ kiểm lenient: P | R |",
                    "|---|---:|---|---|---|---|---|---|---|---|"]
            for g in GROUPS:
                c = [t[s][g] for s in ("tagger_definite", "tagger_with_possible", "checker_strict", "checker_lenient")]
                pos = c[0]["tp"] + c[0]["fn"]
                out.append(f"| {vi[g]} | {pos} | " + " | ".join(f"{fmt(x['precision'])} | {fmt(x['recall'])}" for x in c) + " |")
            out.append("")
    out += ["## Ma trận bất đồng (thẻ chắc chắn so với bộ kiểm strict, toàn bộ mẫu)", "",
            "| Nhóm | Cả hai | Chỉ thẻ | Chỉ bộ kiểm | Không bên nào |", "|---|---:|---:|---:|---:|"]
    out += [f"| {vi[g]} | {d['both']} | {d['tagger_only']} | {d['checker_only']} | {d['neither']} |"
            for g, d in res["disagreement"].items()]
    out += ["", "## Lỗi trên tập dev (nhãn \"Có\"; thẻ chắc chắn; bộ kiểm strict)", "",
            "FN = bỏ sót (nhãn có, máy không); FP = báo nhầm. Tối đa "
            f"{MAX_ERRORS} công thức mỗi loại.", ""]
    for g, e in res["errors"].items():
        if not any(e["counts"].values()):
            continue
        out.append(f"### {vi[g]} — thẻ: FN {e['counts']['tagger_fn']}, FP {e['counts']['tagger_fp']}; "
                   f"bộ kiểm: FN {e['counts']['checker_fn']}, FP {e['counts']['checker_fp']}")
        for kind in ("tagger_fn", "tagger_fp", "checker_fn", "checker_fp"):
            for rid in e[kind]:
                r = res["recipe_text"][str(rid)]
                note = res["label_notes"].get(str(rid), "")
                out.append(f"- **{kind}** {rid} *{r['title']}*: " + "; ".join(r["lines"]) + (f" — ghi chú nhãn: {note}" if note else ""))
        out.append("")
    return "\n".join(out) + "\n"


def main():
    import subprocess
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--iteration", type=int, default=0, help="lexicon tuning rounds already done on the dev split")
    a = p.parse_args()
    with psycopg.connect(config.DATABASE_URL) as conn:
        sample, labels, tags, verdicts, evidence, lines = load(conn)
    res = compute(sample, labels, tags, verdicts)
    errs = errors(sample, labels, tags, verdicts, lines)
    shown = {rid for e in errs.values() for k, v in e.items() if k != "counts" for rid in v}
    flagged = [r for r in evidence if r["contains"] != "no"]
    res.update({
        "ran_at": datetime.now().isoformat(timespec="seconds"), "iteration": a.iteration,
        "git_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                     text=True).stdout.strip(),
        "provenance": json.loads((LABELS / "allergen_gold.provenance.json").read_text(encoding="utf-8")),
        "checker_meta": json.loads((LABELS / "checker_sample.json").read_text(encoding="utf-8")),
        "checker_evidence_ok": rate(sum(r["evidence_ok"] == "True" for r in flagged), len(flagged)),
        "errors": errs,
        "recipe_text": {str(r): lines[r] for r in shown},
        "label_notes": {str(r): labels[r]["note"] for r in shown if labels[r]["note"]},
    })
    (LABELS / "report_allergen.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (LABELS / "report_allergen.md").write_text(render(res), encoding="utf-8")
    print(render(res)[:4000])


if __name__ == "__main__":
    main()
