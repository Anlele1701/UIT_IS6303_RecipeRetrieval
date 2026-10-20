"""M0 spike: can pg_search filter allergen/ingredient columns inside the BM25 and vector index?

    uv run scripts/spike_array_filter.py synthetic   # after `ingest.py load`: one row per Recipe, random vectors
    uv run scripts/spike_array_filter.py real        # after `ingest.py chunk semantic`: real Chunks and embeddings

Everything lives in schema `spike`; the served `chunk` table is never touched. The allergen and
ingredient tags here are crude keyword matches, good enough to give filters realistic selectivity.
They are NOT the M1 tagger. Writes eval/spike/array_filter_<source>.json and .md.

Each filter variant is run for BM25 (`content ||| q ORDER BY pdb.score`) and Dense (`ORDER BY embedding <=> literal`)
at LIMIT 50 and scored on: pushdown (EXPLAIN), completeness, violations, rank fidelity against an exact
plain-SQL answer, and latency.
"""

import argparse
import json
import random
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402

from api import config  # noqa: E402

OUT = ROOT / "eval" / "spike"
SEED = 42
LIMIT = 50
N_QUERIES = 20
REPEATS = 3
TABLE = {"synthetic": "spike.chunk_tag", "real": "spike.chunk_real"}

# Crude keyword tags, spike only: allergen code -> regex over lowercased ingredient lines.
ALLERGEN_RE = {
    "milk": r"\m(milk|butter|cheese|cream|yogurt|buttermilk|parmesan|mozzarella|cheddar|ricotta|whey)\M",
    "egg": r"\m(eggs?|egg whites?|egg yolks?|mayonnaise)\M",
    "fish": r"\m(salmon|tuna|cod|tilapia|anchov(y|ies)|halibut|fish|worcestershire)\M",
    "crustacean_shellfish": r"\m(shrimp|prawns?|crab|lobster|crawfish)\M",
    "tree_nuts": r"\m(almonds?|walnuts?|pecans?|cashews?|pistachios?|hazelnuts?|macadamia|pesto)\M",
    "peanut": r"\m(peanuts?|peanut butter)\M",
    "wheat": r"\m(flour|bread|breadcrumbs|pasta|spaghetti|noodles|tortillas?|crackers?|soy sauce)\M",
    "soy": r"\m(soy|soybeans?|tofu|edamame|miso|soy sauce)\M",
    "sesame": r"\m(sesame|tahini)\M",
}
INGREDIENTS = ["garlic", "onion", "cilantro", "chicken", "beef", "pork", "mushroom", "tomato",
               "bacon", "cinnamon", "lemon", "rice", "potato", "carrot", "celery", "ginger"]

# Constraint sets, from mild to very selective.
FILTERS = {
    "peanut": {"allergens": ["peanut"], "ingredients": []},
    "milk": {"allergens": ["milk"], "ingredients": []},
    "milk_egg_wheat": {"allergens": ["milk", "egg", "wheat"], "ingredients": []},
    "garlic": {"allergens": [], "ingredients": ["garlic"]},
    "peanut_milk_cilantro": {"allergens": ["peanut", "milk"], "ingredients": ["cilantro"]},
}


def where(variant: str, f: dict) -> tuple[str, list]:
    """SQL condition and parameters for one filter variant (spike table columns)."""
    a, i = f["allergens"], f["ingredients"]
    conds, params = [], []
    if variant == "A1_overlap":
        if a:
            conds.append("NOT (allergens && %s::text[])"); params.append(a)
        if i:
            conds.append("NOT (ingredients_norm && %s::text[])"); params.append(i)
    elif variant == "A2_term_set":
        if a:
            conds.append("NOT (allergens @@@ pdb.term_set(%s::text[]))"); params.append(a)
        if i:
            conds.append("NOT (ingredients_norm @@@ pdb.term_set(%s::text[]))"); params.append(i)
    elif variant == "B_bool":
        conds += [f"has_{x} = false" for x in a]
        if i:  # booleans only exist for allergens; ingredients fall back to the term set
            conds.append("NOT (ingredients_norm @@@ pdb.term_set(%s::text[]))"); params.append(i)
    elif variant == "D_combined":  # term set + time + category, the shape M4 will send
        cond, params = where("A2_term_set", f)
        return cond + " AND total_minutes <= 30 AND category = ANY(%s)", params + [CATEGORIES]
    else:
        raise ValueError(variant)
    return " AND ".join(conds) or "true", params


VARIANTS = ["A1_overlap", "A2_term_set", "B_bool", "D_combined"]
CATEGORIES = ["main-dish", "side-dish", "desserts", "soups-stews-and-chili"]  # category slugs as stored


def plain_where(f: dict, combined: bool = False) -> tuple[str, list]:
    """The same constraints in plain SQL, for the exact ground truth outside ParadeDB."""
    conds, params = (["total_minutes <= 30", "category = ANY(%s)"], [CATEGORIES]) if combined else ([], [])
    if f["allergens"]:
        conds.append("NOT (allergens && %s::text[])"); params.append(f["allergens"])
    if f["ingredients"]:
        conds.append("NOT (ingredients_norm && %s::text[])"); params.append(f["ingredients"])
    return " AND ".join(conds) or "true", params


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def build_tags(conn):
    """spike.recipe_tag: crude allergen and ingredient keywords per Recipe, computed in the DB."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS spike")
    conn.execute("DROP TABLE IF EXISTS spike.recipe_tag")
    allergen_cases = " || ".join(
        f"CASE WHEN lines ~* '{rx}' THEN ARRAY['{code}'] ELSE ARRAY[]::text[] END" for code, rx in ALLERGEN_RE.items())
    ingredient_cases = " || ".join(
        f"CASE WHEN lines ~* '\\m{w}s?\\M' THEN ARRAY['{w}'] ELSE ARRAY[]::text[] END" for w in INGREDIENTS)
    conn.execute(f"""
        CREATE TABLE spike.recipe_tag AS
        SELECT recipe_id, {allergen_cases} AS allergens, {ingredient_cases} AS ingredients_norm
        FROM (SELECT recipe_id, lower(string_agg(line, ' ; ')) AS lines
              FROM recipe_ingredient GROUP BY recipe_id) l""")
    conn.execute("ALTER TABLE spike.recipe_tag ADD PRIMARY KEY (recipe_id)")


def build_table(conn, source: str):
    t = TABLE[source]
    conn.execute(f"DROP TABLE IF EXISTS {t}")
    bools = ", ".join(f"'{a}' = ANY(g.allergens) AS has_{a}" for a in ALLERGEN_RE)
    if source == "synthetic":
        conn.execute("SELECT setseed(%s)", [SEED / 100])
        conn.execute(f"""
            CREATE TABLE {t} AS
            SELECT r.id, r.id AS recipe_id,
                   r.title || E'\\n' || coalesce((SELECT string_agg(line, '; ' ORDER BY position)
                                                   FROM recipe_ingredient i WHERE i.recipe_id = r.id), '') AS content,
                   c.name AS category, r.total_minutes, g.allergens, g.ingredients_norm, {bools},
                   (SELECT array_agg(random()::real - 0.5) FROM generate_series(1, 768) WHERE r.id > 0)::vector(768)
                       AS embedding
            FROM recipe r JOIN category c ON c.id = r.category_id JOIN spike.recipe_tag g ON g.recipe_id = r.id""")
    else:
        conn.execute(f"""
            CREATE TABLE {t} AS
            SELECT ch.id, ch.recipe_id, ch.content, ch.category, ch.total_minutes,
                   g.allergens, g.ingredients_norm, {bools}, ch.embedding
            FROM chunk ch JOIN spike.recipe_tag g ON g.recipe_id = ch.recipe_id
            WHERE ch.strategy = 'semantic'""")
    conn.execute(f"ALTER TABLE {t} ADD PRIMARY KEY (id)")
    has = ", ".join(f"has_{a}" for a in ALLERGEN_RE)
    # Same shape as sql/indexes.sql, plus the candidate filter columns.
    conn.execute(f"""
        CREATE INDEX {t.split('.')[1]}_idx ON {t} USING paradedb (
          id, (content::pdb.simple('stemmer=english')), (category::pdb.literal), recipe_id, total_minutes,
          (allergens::pdb.literal), (ingredients_norm::pdb.literal), {has},
          embedding vector_cosine_ops)
        WITH (key_field = 'id')""")
    conn.execute(f"ANALYZE {t}")


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------

def pick_queries(conn, t: str) -> tuple[list[str], list[str]]:
    rnd = random.Random(SEED)
    qs = [json.loads(line)["text"] for line in (ROOT / "eval" / "queries.jsonl").read_text(encoding="utf-8").splitlines()]
    texts = rnd.sample(qs, N_QUERIES)
    ids = [r[0] for r in conn.execute(f"SELECT id FROM {t} ORDER BY id")]
    vec_ids = rnd.sample(ids, N_QUERIES)
    vecs = [conn.execute(f"SELECT embedding::text FROM {t} WHERE id = %s", [i]).fetchone()[0] for i in vec_ids]
    return texts, vecs


def search_sql(t: str, retriever: str, cond: str, limit: int) -> str:
    if retriever == "bm25":
        return (f"SELECT id FROM {t} WHERE content ||| %s AND {cond} "
                f"ORDER BY pdb.score(id) DESC, id LIMIT {limit}")
    return f"SELECT id FROM {t} WHERE id @@@ pdb.all() AND {cond} ORDER BY embedding <=> %s::vector LIMIT {limit}"


def exact_ids(conn, t: str, retriever: str, q: str, f: dict, combined: bool = False) -> list[int]:
    """The right answer, computed without trusting the index to filter."""
    cond, params = plain_where(f, combined)
    if retriever == "bm25":
        # unfiltered BM25 deep enough to hold the filtered top 50, then filtered in SQL outside ParadeDB
        sql = (f"SELECT id FROM (SELECT id, pdb.score(id) AS s FROM {t} WHERE content ||| %s "
               f"ORDER BY s DESC, id LIMIT 100000) x JOIN {t} USING (id) WHERE {cond} ORDER BY s DESC, id LIMIT {LIMIT}")
        return [r[0] for r in conn.execute(sql, [q, *params])]
    # exact cosine over a plain scan (OFFSET 0 keeps ParadeDB out of the subquery)
    sql = (f"SELECT id FROM (SELECT * FROM {t} OFFSET 0) x WHERE {cond} "
           f"ORDER BY embedding <=> %s::vector, id LIMIT {LIMIT}")
    return [r[0] for r in conn.execute(sql, [*params, q])]


def violations(conn, t: str, ids: list[int], f: dict, combined: bool = False) -> int:
    if not ids:
        return 0
    cond, params = plain_where(f, combined)
    return conn.execute(f"SELECT count(*) FROM {t} WHERE id = ANY(%s) AND NOT ({cond})", [ids, *params]).fetchone()[0]


def explain(conn, sql: str, params: list) -> dict:
    plan = "\n".join(r[0] for r in conn.execute("EXPLAIN (VERBOSE, COSTS OFF) " + sql, params))
    tantivy = next((line.split("Tantivy Query:", 1)[1].strip() for line in plan.splitlines() if "Tantivy Query:" in line), "")
    above_scan = plan.split("Custom Scan (ParadeDB", 1)[0]
    return {
        "custom_scan": "ParadeDB" in plan,
        "topk": "TopKScanExecState" in plan,
        "heap_filter": "heap_filter" in tantivy,
        "postgres_filter_above": "Filter:" in above_scan or "Sort Key" in above_scan,
        "plan": plan,
    }


def measure(conn, t: str, texts: list[str], vecs: list[str]) -> list[dict]:
    rows = []
    for retriever, queries in (("bm25", texts), ("dense", vecs)):
        # unfiltered baseline: latency and, for Dense, ANN overlap with exact search
        base_ms, base_overlap = [], []
        for q in queries:
            sql = search_sql(t, retriever, "true", LIMIT)
            for _ in range(REPEATS):
                s = time.perf_counter()
                got = [r[0] for r in conn.execute(sql, [q])]
                base_ms.append((time.perf_counter() - s) * 1000)
            ex = exact_ids(conn, t, retriever, q, {"allergens": [], "ingredients": []})
            base_overlap.append(len(set(got) & set(ex)) / max(len(ex), 1))
        rows.append({"retriever": retriever, "variant": "none", "filter": "none",
                     "p50_ms": round(statistics.median(base_ms), 1),
                     "overlap_exact": round(statistics.mean(base_overlap), 3)})
        for fname, f in FILTERS.items():
            for variant in VARIANTS:
                cond, params = where(variant, f)
                sql = search_sql(t, retriever, cond, LIMIT)
                combined = variant == "D_combined"
                try:
                    args = (lambda q: [q, *params]) if retriever == "bm25" else (lambda q: [*params, q])
                    plan = explain(conn, sql, args(queries[0]))
                    ms, short, viol, overlap, exact_n = [], 0, 0, [], []
                    for q in queries:
                        for _ in range(REPEATS):
                            s = time.perf_counter()
                            got = [r[0] for r in conn.execute(sql, args(q))]
                            ms.append((time.perf_counter() - s) * 1000)
                        exact = exact_ids(conn, t, retriever, q, f, combined)
                        exact_n.append(len(exact))
                        short += len(got) < len(exact)
                        viol += violations(conn, t, got, f, combined)
                        if exact:  # an empty right answer says nothing about the filter
                            overlap.append(len(set(got) & set(exact)) / len(exact))
                    rows.append({
                        "retriever": retriever, "variant": variant, "filter": fname,
                        "pushdown": plan["custom_scan"] and not plan["postgres_filter_above"],
                        "native_index_filter": plan["custom_scan"] and not plan["heap_filter"]
                                               and not plan["postgres_filter_above"],
                        "heap_filter": plan["heap_filter"], "topk": plan["topk"],
                        "queries_short": short, "violations": viol,
                        "overlap_exact": round(statistics.mean(overlap), 3) if overlap else None,
                        "queries_empty": sum(n == 0 for n in exact_n),
                        "exact_min_results": min(exact_n),
                        "p50_ms": round(statistics.median(ms), 1),
                        "plan": plan["plan"],
                    })
                except psycopg.Error as e:
                    rows.append({"retriever": retriever, "variant": variant, "filter": fname,
                                 "error": str(e).splitlines()[0]})
                print(f"{retriever:5} {variant:12} {fname:22} {rows[-1].get('error') or rows[-1]['p50_ms']}",
                      flush=True)
    return rows


def selectivity(conn, t: str) -> dict:
    total = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    out = {"rows": total}
    for fname, f in FILTERS.items():
        cond, params = plain_where(f)
        n = conn.execute(f"SELECT count(*) FROM {t} WHERE {cond}", params).fetchone()[0]
        out[fname] = {"kept": n, "kept_share": round(n / total, 3)}
    return out


def verdict(rows: list[dict]) -> dict:
    """Which variants pass criteria 1-4 on both retrievers. A row whose right answer is empty for
    every query is not measured, and a variant with such a row does not pass."""
    out = {}
    for variant in VARIANTS:
        rs = [r for r in rows if r["variant"] == variant]
        unmeasured = sum("error" not in r and r["overlap_exact"] is None for r in rs)
        ok = not unmeasured and all(
            "error" not in r and r["pushdown"] and r["violations"] == 0 and r["queries_short"] == 0
            and (r["retriever"] == "dense" or r["overlap_exact"] == 1.0) for r in rs)
        out[variant] = {"passes": ok, "errors": sum("error" in r for r in rs), "unmeasured_rows": unmeasured,
                        "native": all(r.get("native_index_filter") for r in rs),
                        "min_dense_overlap": min((r["overlap_exact"] for r in rs
                                                  if r["retriever"] == "dense" and "error" not in r and r["overlap_exact"] is not None),
                                                 default=None)}
    return out


def render(res: dict) -> str:
    lines = [f"# Spike lọc mảng pg_search – nguồn `{res['source']}`", "",
             f"Sinh tự động bởi `scripts/spike_array_filter.py` lúc {res['ran_at']}. pg_search {res['pg_search']}, "
             f"probe {res['probe']}, LIMIT {LIMIT}, {N_QUERIES} truy vấn × {REPEATS} lần, seed {SEED}.", "",
             "## Độ chọn lọc của bộ lọc", "", "| Bộ lọc | Số dòng còn lại | Tỉ lệ |", "|---|---:|---:|"]
    sel = res["selectivity"]
    lines += [f"| {k} | {v['kept']:,} / {sel['rows']:,} | {v['kept_share']:.1%} |" for k, v in sel.items() if k != "rows"]
    lines += ["", "## Kết quả theo biến thể", "",
              "| Retriever | Biến thể | Bộ lọc | Pushdown | Lọc native | heap_filter | TopK | Đáp án rỗng | Truy vấn hụt | Vi phạm | Overlap với exact | p50 ms |",
              "|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|"]
    for r in res["rows"]:
        if "error" in r:
            lines.append(f"| {r['retriever']} | {r['variant']} | {r['filter']} | LỖI: {r['error'][:80]} ||||||||| |")
        elif r["variant"] == "none":
            lines.append(f"| {r['retriever']} | (không lọc) | – | | | | | | | | {r['overlap_exact']} | {r['p50_ms']} |")
        else:
            y = lambda b: "có" if b else "không"  # noqa: E731
            lines.append(f"| {r['retriever']} | {r['variant']} | {r['filter']} | {y(r['pushdown'])} | "
                         f"{y(r['native_index_filter'])} | {y(r['heap_filter'])} | {y(r['topk'])} | "
                         f"{r['queries_empty']}/{N_QUERIES} | {r['queries_short']} | {r['violations']} | "
                         f"{'không đo được' if r['overlap_exact'] is None else r['overlap_exact']} | {r['p50_ms']} |")
    lines += ["", "## Đánh giá theo luật quyết định (tiêu chí 1–4)", "",
              "| Biến thể | Đạt | Lọc native trong index | Overlap dense thấp nhất | Dòng không đo được | Lỗi |",
              "|---|---|---|---:|---:|---:|"]
    for v, d in res["verdict"].items():
        lines.append(f"| {v} | {'có' if d['passes'] else 'không'} | {'có' if d['native'] else 'không'} | "
                     f"{d['min_dense_overlap']} | {d['unmeasured_rows']} | {d['errors']} |")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", choices=list(TABLE))
    p.add_argument("--skip-build", action="store_true", help="reuse the spike table already built")
    a = p.parse_args()
    t = TABLE[a.source]
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        if not a.skip_build:
            started = time.perf_counter()
            build_tags(conn)
            build_table(conn, a.source)
            print(f"built {t} in {time.perf_counter() - started:.0f} s", flush=True)
        texts, vecs = pick_queries(conn, t)
        res = {"source": a.source, "table": t, "ran_at": datetime.now().isoformat(timespec="seconds"), "seed": SEED,
               "limit": LIMIT, "queries": N_QUERIES, "repeats": REPEATS,
               "pg_search": conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'pg_search'").fetchone()[0],
               "probe": conn.execute("SHOW paradedb.vector_cluster_max_probe").fetchone()[0],
               "filters": FILTERS, "selectivity": selectivity(conn, t)}
        res["rows"] = measure(conn, t, texts, vecs)
        res["verdict"] = verdict(res["rows"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"array_filter_{a.source}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / f"array_filter_{a.source}.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
