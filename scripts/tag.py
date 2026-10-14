"""Data pipeline rules D1-D8: tag every Recipe and count what each rule did.

    uv run scripts/tag.py run      # parse, normalize and tag all lines; write the tag tables and the report
    uv run scripts/tag.py report   # rebuild docs/corpus_report.md from eval/corpus.json

`run` replaces the contents of allergen, ingredient, ingredient_allergen, ingredient_alias_vi,
recipe_ingredient_norm and recipe_tag in one transaction (derived data, rebuilt from the recipe tables
and data/lexicon/). It never touches chunk: `ingest.py retag <strategy>` copies the tags there.
Writes eval/corpus.json (counts per rule, lexicon hashes, commit) and docs/corpus_report.md.
D1-D3 are recounted from data/recipe.csv with the same rules `ingest.py load` applies.
"""

import argparse
import collections
import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import psycopg  # noqa: E402

import ingest  # noqa: E402
from api import config  # noqa: E402
from lexicon.normalize import LEXICON, Lexicon  # noqa: E402
from lexicon.parse import parse_line  # noqa: E402
from lexicon.tagger import ALLERGENS, Rules, tag_recipe  # noqa: E402

OUT_JSON = ROOT / "eval" / "corpus.json"
OUT_MD = ROOT / "docs" / "corpus_report.md"
LEXICON_FILES = ["allergens.csv", "rules.csv", "manual_synonyms.csv", "ingredients.csv", "allergen_map.csv",
                 "vi_alias.csv"]
SEED = 42  # nothing here samples; recorded for the run settings convention
TOP_UNKNOWN = 50
BASE_COLUMNS = {"title", "url", "category", "author", "description", "rating", "rating_count", "review_count",
                "ingredients", "directions", "prep_time", "cook_time", "total_time", "servings", "yields",
                "instructions_list", "image"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_commit() -> str | None:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or None


# ---------------------------------------------------------------------------
# D1-D3 from the source CSV
# ---------------------------------------------------------------------------

def source_rules() -> dict:
    with open(ingest.CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    seen, kept = set(), []
    for r in rows:
        if r["url"] not in seen:
            seen.add(r["url"])
            kept.append(r)
    dropped = [c for c in rows[0] if c not in BASE_COLUMNS and c not in ingest.NUTRITION]
    empty_share = {c: round(sum(1 for r in rows if not r[c].strip()) / len(rows), 4) for c in dropped}
    times = {}
    for col in ("prep_time", "cook_time", "total_time"):
        empty = sum(1 for r in kept if not r[col].strip())
        unreadable = sum(1 for r in kept if r[col].strip() and ingest.parse_minutes(r[col]) is None)
        times[col] = {"source_empty": empty, "unreadable": unreadable, "null": empty + unreadable}
    return {
        "D1": {"rule": "drop rows whose url repeats an earlier row", "csv_rows": len(rows),
               "duplicate_urls_dropped": len(rows) - len(kept), "recipes": len(kept)},
        "D2": {"rule": "drop nutrition columns more than 99% empty", "columns_dropped": len(dropped),
               "empty_share": empty_share, "all_over_99pct": all(v > 0.99 for v in empty_share.values())},
        "D3": {"rule": 'parse "1 hr 10 mins" to minutes; null when empty or unreadable', "per_column": times},
    }


# ---------------------------------------------------------------------------
# D4-D8
# ---------------------------------------------------------------------------

def read_csv(name: str) -> list[dict]:
    with open(LEXICON / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tag_all(conn) -> tuple[dict, dict]:
    lex, rules = Lexicon.from_csv(), Rules.from_csv()
    ingredients = read_csv("ingredients.csv")
    tags = {r["canonical"]: rules.tags(r["canonical"]) for r in ingredients}
    groups = {c: t.group for c, t in tags.items()}
    allergens = {c: t.allergens for c, t in tags.items()}
    ids = {r["canonical"]: i for i, r in enumerate(ingredients, 1)}

    lines = conn.execute("SELECT recipe_id, position, line FROM recipe_ingredient ORDER BY recipe_id, position").fetchall()
    parsed: dict[str, tuple] = {}
    norm_rows, per_recipe = [], collections.defaultdict(list)
    status, unknown_names = collections.Counter(), collections.Counter()
    for rid, pos, line in lines:
        if line not in parsed:
            p = parse_line(line)
            parsed[line] = (p, lex.match(p.name) if p.name else [])
        p, found = parsed[line]
        status[p.status] += 1
        if not found:
            unknown_names[p.name or line] += 1
        per_recipe[rid].append(found)
        norm_rows.append((rid, pos, p.name, p.quantity, p.unit, p.status, [ids[c] for c in found]))

    recipe_ids = [r[0] for r in conn.execute("SELECT id FROM recipe ORDER BY id")]
    tag_rows, counts = [], collections.Counter()
    by_allergen = {a: {"recipes": 0, "only_hidden": 0} for a in ALLERGENS}
    for rid in recipe_ids:
        t = tag_recipe(per_recipe.get(rid, []), groups, allergens)
        tag_rows.append((rid, list(t.allergens), list(t.ingredients_norm), list(t.diet_flags), t.has_unknown,
                         t.unknown_lines))
        counts["vegetarian"] += "vegetarian" in t.diet_flags
        counts["vegan"] += "vegan" in t.diet_flags
        counts["has_unknown"] += t.has_unknown
        counts["no_allergen"] += not t.allergens
        for a in t.allergens:
            by_allergen[a]["recipes"] += 1
            kinds = {allergens[c][a] for c in t.ingredients_norm if a in allergens.get(c, {})}
            by_allergen[a]["only_hidden"] += kinds == {"hidden"}

    total_lines = len(lines)
    mapped = total_lines - sum(unknown_names.values())
    hit = collections.Counter(c for found in (parsed[l][1] for _, _, l in lines) for c in found)
    origin = collections.Counter(r["origin"] for r in ingredients)
    n = len(recipe_ids)
    report = {
        "D4": {"rule": "parse a line into quantity, unit, name, note (rule-based)", "lines": total_lines,
               "distinct_lines": len(parsed), "status": dict(status),
               "status_share": {k: round(v / total_lines, 4) for k, v in status.items()}},
        "D5": {"rule": "map the parsed name to canonical ingredients (longest synonym first)",
               "canonicals": len(ingredients), "canonicals_by_origin": dict(origin),
               "canonicals_used": len(hit), "lines_mapped": mapped, "coverage": round(mapped / total_lines, 4),
               "multi_ingredient_lines": sum(1 for _, _, l in lines if len(parsed[l][1]) > 1)},
        "D6": {"rule": "allergen groups per canonical (FDA 9; rules.csv; hidden ingredients conservative)",
               "recipes": n, "per_allergen": {a: {**v, "share": round(v["recipes"] / n, 4)} for a, v in by_allergen.items()},
               "recipes_without_allergen": counts["no_allergen"]},
        "D7": {"rule": "vegetarian: no animal group or fish/crustacean tag; vegan: also no dairy/egg/honey or milk/egg tag",
               "vegetarian": counts["vegetarian"], "vegan": counts["vegan"],
               "vegetarian_share": round(counts["vegetarian"] / n, 4), "vegan_share": round(counts["vegan"] / n, 4)},
        "D8": {"rule": "a line with no canonical ingredient is unknown; does not change tags by default",
               "unknown_lines": sum(unknown_names.values()), "recipes_with_unknown": counts["has_unknown"],
               "recipes_with_unknown_share": round(counts["has_unknown"] / n, 4),
               "top_unknown": unknown_names.most_common(TOP_UNKNOWN)},
    }
    tables = {"ingredients": ingredients, "ids": ids, "tags": tags, "norm_rows": norm_rows, "tag_rows": tag_rows}
    return report, tables


def write_tables(conn, t: dict):
    allergens = read_csv("allergens.csv")
    aliases = read_csv("vi_alias.csv")
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("TRUNCATE recipe_tag, recipe_ingredient_norm, ingredient_alias_vi, ingredient_allergen, "
                    "ingredient, allergen RESTART IDENTITY")
        cur.executemany("INSERT INTO allergen VALUES (%s, %s, %s, %s)",
                        [(a["code"], a["name_en"], a["name_vi"], a["source"]) for a in allergens])
        with cur.copy("COPY ingredient (id, canonical_name, synonyms, grp) FROM STDIN") as cp:  # COPY keeps given ids
            for r in t["ingredients"]:
                cp.write_row((t["ids"][r["canonical"]], r["canonical"], [s for s in r["synonyms"].split("|") if s],
                              t["tags"][r["canonical"]].group))
        cur.execute("SELECT setval(pg_get_serial_sequence('ingredient', 'id'), (SELECT max(id) FROM ingredient))")
        with cur.copy("COPY ingredient_allergen FROM STDIN") as cp:
            for c, tg in t["tags"].items():
                for a, kind in tg.allergens.items():
                    cp.write_row((t["ids"][c], a, kind))
        with cur.copy("COPY ingredient_alias_vi (alias, ingredient_id, allergen_code) FROM STDIN") as cp:
            for a in aliases:
                ing = t["ids"][a["target"]] if a["target_type"] == "ingredient" else None
                cp.write_row((a["alias"], ing, a["target"] if a["target_type"] == "allergen" else None))
        with cur.copy("COPY recipe_ingredient_norm FROM STDIN") as cp:
            for row in t["norm_rows"]:
                cp.write_row(row)
        with cur.copy("COPY recipe_tag FROM STDIN") as cp:
            for row in t["tag_rows"]:
                cp.write_row(row)


def render(c: dict) -> str:
    d1, d2, d3, d4, d5, d6, d7, d8 = (c[k] for k in ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"))
    pct = lambda x: f"{x:.1%}".replace(".", ",")  # noqa: E731
    num = lambda x: f"{x:,}".replace(",", ".")  # noqa: E731
    vi = {"milk": "sữa", "egg": "trứng", "fish": "cá", "crustacean_shellfish": "giáp xác", "tree_nuts": "hạt cây",
          "peanut": "đậu phộng", "wheat": "lúa mì", "soy": "đậu nành", "sesame": "mè"}
    lines = [
        "# Báo cáo dữ liệu (quy tắc D1–D8)", "",
        f"Sinh tự động bởi `scripts/tag.py` lúc {c['ran_at']} (commit `{c['git_commit']}`). Số liệu gốc ở "
        "`eval/corpus.json`. Không sửa tay file này.", "",
        "| Mã | Quy tắc | Số liệu |", "|---|---|---|",
        f"| D1 | Loại công thức trùng URL | {num(d1['csv_rows'])} dòng CSV → bỏ {d1['duplicate_urls_dropped']} → "
        f"{num(d1['recipes'])} công thức |",
        f"| D2 | Bỏ cột dinh dưỡng rỗng > 99% | {d2['columns_dropped']} cột, tỉ lệ rỗng thấp nhất "
        f"{pct(min(d2['empty_share'].values()))} |",
        f"| D3 | Chuẩn hóa thời gian → phút | `total_time` null: {num(d3['per_column']['total_time']['null'])} "
        f"(rỗng ở nguồn {num(d3['per_column']['total_time']['source_empty'])}, không đọc được "
        f"{d3['per_column']['total_time']['unreadable']}) |",
        f"| D4 | Tách dòng nguyên liệu | {num(d4['lines'])} dòng: ok {pct(d4['status_share'].get('ok', 0))}, "
        f"partial {pct(d4['status_share'].get('partial', 0))}, fail {pct(d4['status_share'].get('fail', 0))} |",
        f"| D5 | Ánh xạ sang nguyên liệu chuẩn | {num(d5['canonicals'])} canonical; {pct(d5['coverage'])} số dòng "
        f"ánh xạ được; {num(d5['multi_ingredient_lines'])} dòng chứa nhiều nguyên liệu |",
        f"| D6 | Gắn nhóm dị ứng (FDA 9) | {num(d6['recipes'] - d6['recipes_without_allergen'])} công thức có ≥ 1 nhóm |",
        f"| D7 | Cờ chế độ ăn | vegetarian {num(d7['vegetarian'])} ({pct(d7['vegetarian_share'])}), "
        f"vegan {num(d7['vegan'])} ({pct(d7['vegan_share'])}) |",
        f"| D8 | Dòng `unknown` | {num(d8['unknown_lines'])} dòng; {num(d8['recipes_with_unknown'])} công thức "
        f"({pct(d8['recipes_with_unknown_share'])}) có ≥ 1 dòng unknown |",
        "", "## Phân bố nhóm dị ứng (D6)", "",
        "| Nhóm | Số công thức | Tỉ lệ | Chỉ do thành phần ẩn |", "|---|---:|---:|---:|",
    ]
    for a, v in d6["per_allergen"].items():
        lines.append(f"| {a} ({vi[a]}) | {num(v['recipes'])} | {pct(v['share'])} | {num(v['only_hidden'])} |")
    lines += ["", f"## {TOP_UNKNOWN} tên `unknown` phổ biến nhất (D8)", "", "| Tên sau khi parse | Số dòng |", "|---|---:|"]
    lines += [f"| {name} | {n} |" for name, n in d8["top_unknown"]]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["run", "report"])
    a = p.parse_args()
    if a.command == "run":
        started = time.time()
        corpus = {"ran_at": datetime.now().isoformat(timespec="seconds"), "git_commit": git_commit(), "seed": SEED,
                  "lexicon_sha256": {f: sha256(LEXICON / f) for f in LEXICON_FILES}, **source_rules()}
        with psycopg.connect(config.DATABASE_URL) as conn:
            report, tables = tag_all(conn)
            write_tables(conn, tables)
        corpus.update(report)
        corpus["seconds"] = round(time.time() - started, 1)
        OUT_JSON.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    corpus = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    OUT_MD.write_text(render(corpus), encoding="utf-8")
    print(render(corpus))


if __name__ == "__main__":
    main()
