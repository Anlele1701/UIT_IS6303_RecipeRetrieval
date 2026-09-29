"""Evaluation run: score retrieval configs on the Query set under every loaded Chunking strategy.

    uv run scripts/evaluate.py                                    # every config, every loaded strategy
    uv run scripts/evaluate.py --configs dense --strategies fixed --limit 20
    uv run scripts/evaluate.py --arm rerank-top-20                # an Ablation run, see ARMS

Configs: sparse, dense, fusion (the Fusion baseline: the candidates Hybrid would rerank, in RRF order;
eval only) and hybrid (RRF + Reranking, as the API serves it). Both call the API's own Hybrid code.

Prints a markdown table and writes a run folder under eval/runs/<timestamp>/:
settings.json, metrics.json, metrics.csv, per_query.csv (ranks, latencies, the winning Chunk kind), table.md,
recipes.csv (titles of every ranked Recipe) and corpus.json (what was searched). Config order rotates per query.

Scored against the pooled qrels (eval/qrels.csv): a rank is the first right Recipe's, where a query's right
Recipes are the one it was written from plus any judged relevant. --qrels none scores the written-from Recipe only.
Runs in the project env (not a PEP 723 script) because it calls the API's retrieval code.
"""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # `uv run scripts/evaluate.py` puts scripts/ on the path, not the repo root

import httpx  # noqa: E402
import psycopg  # noqa: E402

import metrics  # noqa: E402
from api import config, retrieval, strategies  # noqa: E402
from api.embed import embed_query  # noqa: E402
from api.filters import SearchParams, where_clause  # noqa: E402

QUERY_SET = ROOT / "eval" / "queries.jsonl"
QRELS = ROOT / "eval" / "qrels.csv"
RUNS = ROOT / "eval" / "runs"
POOL = 50  # Chunks Sparse and Dense pull before deduping; same depth as each list in Fusion and Hybrid

Embedder = Callable[[str], str]  # query text -> pgvector literal
Scorer = Callable[[str, list[str]], list[float]]  # the reranker: query, Chunk texts -> scores


class Stopwatch(dict):
    """Stage name -> milliseconds, on a monotonic clock."""

    @contextmanager
    def __call__(self, stage: str):
        started = time.perf_counter()
        yield
        self[stage] = (time.perf_counter() - started) * 1000


@dataclass(frozen=True)
class SearchInput:
    params: SearchParams
    qvec: str | None  # the query embedding, if any config needs it
    scorer: Scorer | None  # the reranker, if Hybrid runs
    rrf_k: int | None = None  # None: the served setting
    rerank_top: int | None = None
    dense_search: Callable | None = None  # None: the served Dense SQL


# A config's search takes a SearchInput, times its own stages, and returns ranked Chunks.

def sparse(conn, q: SearchInput, watch):
    with watch("sparse"):
        return retrieval.sparse(conn, q.params, POOL)


def dense(conn, q: SearchInput, watch):
    with watch("dense"):
        return (q.dense_search or retrieval.dense)(conn, q.params, q.qvec, POOL)


def fusion(conn, q: SearchInput, watch):
    return retrieval.fused_candidates(conn, q.params, q.qvec, watch, rrf_k=q.rrf_k, rerank_top=q.rerank_top,
                                      dense_search=q.dense_search)


def hybrid(conn, q: SearchInput, watch):
    return retrieval.hybrid(conn, q.params, q.qvec, q.scorer, watch, rrf_k=q.rrf_k, rerank_top=q.rerank_top,
                            dense_search=q.dense_search)


@dataclass(frozen=True)
class EvalConfig:
    search: Callable[..., list[retrieval.Candidate]]  # (conn, SearchInput, Stopwatch) -> ranked Chunks
    stages: tuple[str, ...]  # its latency is the sum of these; "embed" means it needs the query embedding


CONFIGS = {
    "sparse": EvalConfig(sparse, ("sparse",)),
    "dense": EvalConfig(dense, ("embed", "dense")),
    "fusion": EvalConfig(fusion, ("embed", "sparse", "dense", "rrf")),
    "hybrid": EvalConfig(hybrid, ("embed", "sparse", "dense", "rrf", "rerank")),
}
STAGES = list(dict.fromkeys(st for c in CONFIGS.values() for st in c.stages))  # CSV column order

# Ablation run arms: each runs its configs twice per query, as "default" and as "arm" with these settings.
# rerank_model: the arm's reranker, loaded by the command; probe: paradedb.vector_cluster_max_probe for Dense;
# dense_index: "hnsw" searches a pgvector HNSW index (sql/ablation/hnsw.sql) at hnsw.ef_search = ef_search.
ARMS = {
    "reranker-minilm-l6": {"configs": ["hybrid"], "set": {"rerank_model": "cross-encoder/ms-marco-MiniLM-L6-v2"}},
    "reranker-mxbai-base": {"configs": ["hybrid"], "set": {"rerank_model": "mixedbread-ai/mxbai-rerank-base-v1"}},
    "reranker-bge-v2-m3": {"configs": ["hybrid"], "set": {"rerank_model": "BAAI/bge-reranker-v2-m3"}},
    "rrf-k-10": {"configs": ["fusion"], "set": {"rrf_k": 10}},
    "rrf-k-100": {"configs": ["fusion"], "set": {"rrf_k": 100}},
    "rerank-top-20": {"configs": ["hybrid"], "set": {"rerank_top": 20}},
    "rerank-top-100": {"configs": ["hybrid"], "set": {"rerank_top": 100}},
    "exact-dense": {"configs": ["dense", "fusion", "hybrid"], "set": {"probe": 1.0}},
    "hnsw-dense": {"configs": ["dense", "fusion", "hybrid"], "set": {"dense_index": "hnsw", "ef_search": 200}},
}
PROBE = "paradedb.vector_cluster_max_probe"

# The served Dense SQL without `id @@@ pdb.all()`, which is what routes it through the ParadeDB index.
HNSW_DENSE_SQL = """SELECT {columns}, 1 - (embedding <=> %s::vector) AS score
                    FROM chunk WHERE {where}
                    ORDER BY embedding <=> %s::vector LIMIT %s"""


def hnsw_dense(conn, params, qvec: str, limit: int) -> list[retrieval.Candidate]:
    """Dense retrieval for the hnsw-dense arm: same ranking as the served SQL, planned onto the HNSW index."""
    where, wparams = where_clause(params)
    sql = HNSW_DENSE_SQL.format(columns=retrieval.COLUMNS, where=where)
    return retrieval._rows(conn, sql, [qvec, *wparams, qvec, limit])


DENSE_SEARCH = {"hnsw": hnsw_dense}


def hnsw_indexes(conn, strategy_names: list[str]) -> list[dict]:
    """The HNSW index each strategy's partition is searched through, checked with EXPLAIN before any timing.

    Raises ValueError if a partition has no HNSW index or the planner doesn't pick it, so the arm never
    silently measures a sequential scan.
    """
    out = []
    for name in strategy_names:
        partition = f"chunk_{name}"
        indexes = conn.execute(
            """SELECT c.relname, pg_relation_size(c.oid), c.reloptions FROM pg_index i
               JOIN pg_class c ON c.oid = i.indexrelid JOIN pg_am am ON am.oid = c.relam
               WHERE i.indrelid = %s::regclass AND am.amname = 'hnsw'""", [partition]).fetchall()
        qvec = conn.execute(f'SELECT embedding::text FROM "{partition}" LIMIT 1').fetchone()[0]
        where, wparams = where_clause(SearchParams(q="plan check", strategy=name, k=config.MAX_K))
        sql = HNSW_DENSE_SQL.format(columns=retrieval.COLUMNS, where=where)
        plan = "\n".join(r[0] for r in conn.execute("EXPLAIN " + sql, [qvec, *wparams, qvec, POOL]).fetchall())
        used = [ix for ix in indexes if ix[0] in plan.split()]
        if not used:
            scans = "; ".join(line.strip() for line in plan.splitlines() if "Scan" in line)
            raise ValueError(f"the HNSW Dense SQL doesn't use an HNSW index on {partition} (plan: {scans}); "
                             f"build them with sql/ablation/hnsw.sql")
        index, size, options = used[0]
        out.append({"partition": partition, "index": index, "bytes": size, "options": options})
    return out


def any_stage(configs, stage: str) -> bool:
    return any(stage in CONFIGS[c].stages for c in configs)


def rotated(items: list, i: int) -> list:
    """items starting at position i mod len, so across queries each config takes a turn going first.

    A fixed order let later configs run on a cache the earlier ones warmed, which skewed stage times.
    """
    start = i % len(items)
    return items[start:] + items[:start]


def read_queries(path: Path, limit: int | None = None) -> list[dict]:
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return lines[:limit] if limit else lines


def search_all(conn, queries: list[dict], strategy_names: list[str], configs: list[str], embedder: Embedder,
               scorer: Scorer | None, arm: dict | None = None, arm_scorer: Scorer | None = None,
               right: dict[str, set[int]] | None = None):
    """Ranked Recipe ids, stage timings and best Chunk kind per variant, then per (config, strategy, query id).

    The best Chunk kind is the kind of the first right Recipe's top Chunk in the list, or "" if none is in the top.

    Without an arm the only variant is "default". With one, each config also runs as "arm" with the arm's
    settings, interleaved with its default per query so both see the same machine state.

    The first query runs once more as an uncounted warm-up, so caches, connections and the reranker are hot.
    The config order rotates per query (see `rotated`).
    Each query is embedded once and shared by every strategy and config that needs it.
    """
    variants = ["default", "arm"] if arm else ["default"]
    ranked = {v: {} for v in variants}
    timings = {v: {} for v in variants}
    kinds = {v: {} for v in variants}
    sets = {"default": {}, "arm": arm["set"] if arm else {}}
    probes = {"default": _db_settings(conn)["vector_cluster_max_probe"], "arm": sets["arm"].get("probe")}
    pairs = [(c, v) for c in configs for v in variants]
    needs_embedding = any_stage(configs, "embed")
    for i, q in enumerate([queries[0], *queries]):
        query_watch, qvec = Stopwatch(), None
        if needs_embedding:
            with query_watch("embed"):
                qvec = embedder(q["text"])
        for strategy in strategy_names:
            # k=MAX_K: served Hybrid cuts to k, and the eval wants its full list to dedupe
            params = SearchParams(q=q["text"], strategy=strategy, k=config.MAX_K)
            for c, v in rotated(pairs, i):
                knobs = sets[v]
                query = SearchInput(params, qvec, arm_scorer if "rerank_model" in knobs else scorer,
                                    rrf_k=knobs.get("rrf_k"), rerank_top=knobs.get("rerank_top"),
                                    dense_search=DENSE_SEARCH.get(knobs.get("dense_index")))
                if probes["arm"] is not None:  # outside the stopwatch, and paid by both variants alike
                    conn.execute("SELECT set_config(%s, %s, false)", [PROBE, str(probes[v])])
                ef_search = knobs.get("ef_search")
                with conn.transaction() if ef_search else nullcontext():  # SET LOCAL ends with the call
                    if ef_search:
                        conn.execute(f"SET LOCAL hnsw.ef_search = {int(ef_search)}")
                    watch = Stopwatch()
                    hits = CONFIGS[c].search(conn, query, watch)
                if i == 0:
                    continue
                if "embed" in CONFIGS[c].stages:
                    watch["embed"] = query_watch["embed"]
                key = (c, strategy, q["query_id"])
                ranked[v][key] = metrics.dedupe(h.recipe_id for h in hits)
                timings[v][key] = watch
                wanted = right[q["query_id"]] if right else {q["recipe_id"]}
                found = metrics.first_rank(wanted, ranked[v][key])
                kinds[v][key] = next(h.kind for h in hits if h.recipe_id == ranked[v][key][found - 1]) if found else ""
    if probes["arm"] is not None:
        conn.execute("SELECT set_config(%s, %s, false)", [PROBE, str(probes["default"])])
    return ranked, timings, kinds


def resolve_strategies(conn, chosen: list[str] | None) -> list[str]:
    """The chosen strategies if all are loaded, else every loaded one, as the API lists them."""
    if not chosen:
        return [s["name"] for s in strategies.loaded(conn)]
    registry = strategies.registry(conn)
    problems = [p for name in chosen if (p := strategies.strategy_problem(name, registry))]
    if problems:
        raise ValueError("; ".join(problems))
    return chosen


def summarize(relevant, ranked, timings, variant: str = "default") -> list[dict]:
    rows = []
    for (c, s), scores in metrics.metrics_table(relevant, ranked).items():
        keys = [k for k in timings if k[:2] == (c, s)]
        watches = [timings[k] for k in keys]
        latency = {"total": metrics.latency_summary(sum(w.values()) for w in watches)}
        for stage in CONFIGS[c].stages:
            latency[stage] = metrics.latency_summary(w[stage] for w in watches)
        short = sum(len(ranked[k]) < metrics.DEPTH for k in keys)
        rows.append({"config": c, "variant": variant, "strategy": s, **scores, "short_lists": short,
                     "latency_ms": latency})
    return rows


def markdown(rows: list[dict]) -> str:
    head = ["Config", "Strategy", *(metrics.LABELS[m] for m in metrics.COLUMNS), "p50 ms", "p95 ms"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * 2 + "---:|" * (len(head) - 2)]
    for r in rows:
        total = r["latency_ms"]["total"]
        label = r["config"] if r["variant"] == "default" else f"{r['config']} ({r['variant']})"
        cells = [label, r["strategy"], *(f"{r[m]:.3f}" for m in metrics.COLUMNS),
                 f"{total['p50_ms']:.1f}", f"{total['p95_ms']:.1f}"]
        lines.append("| " + " | ".join(cells) + " |")
    n = rows[0]["queries"] if rows else 0
    short = [f"{r['config']}/{r['strategy']} {r['short_lists']}" for r in rows if r["short_lists"]]
    note = (f"\nQueries whose list had fewer than {metrics.DEPTH} unique Recipes (the missing positions count as "
            f"misses): {', '.join(short)}.\n" if short else "")
    return (f"{n} queries. Ranks over the top {metrics.DEPTH} unique Recipes.\n\n" + "\n".join(lines) + "\n"
            + note)


def _git_commit() -> str | None:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or None


def _db_settings(conn) -> dict:
    """What the database contributes to a result: the pg_search build and the Dense ANN probe."""
    version = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'pg_search'").fetchone()
    probe = conn.execute("SHOW paradedb.vector_cluster_max_probe").fetchone()
    return {"pg_search_version": version[0] if version else None, "vector_cluster_max_probe": float(probe[0])}


def sorted_rows(ranked: dict) -> list:
    """(variant, key, ranked ids) in a fixed order: query, strategy, config, variant. Rotation doesn't leak in."""
    order = {c: n for n, c in enumerate(CONFIGS)}
    rows = [(v, k, top) for v, by_key in ranked.items() for k, top in by_key.items()]
    return sorted(rows, key=lambda r: (r[1][2], r[1][1], order[r[1][0]], r[0] != "default"))


STEP_BIN = 50  # characters per bin in corpus.json's Step length histogram


def corpus(conn, strategy_names: list[str], relevant: dict[str, int]) -> dict:
    """What was searched: counts, each strategy's parameters, Chunks per kind and Step length in characters.

    Characters, not tokens, because fixed cuts by tokens and semantic by characters. Step text excludes the
    "<title>\n" line every Chunk starts with.
    """
    one = lambda sql, params=(): conn.execute(sql, params).fetchone()  # noqa: E731
    params = {s["name"]: s["parameters"] for s in strategies.loaded(conn)}
    out = {"recipes": one("SELECT count(*) FROM recipe")[0], "categories": one("SELECT count(*) FROM category")[0],
           "strategies": {}}
    step_len = "length(content) - position(E'\\n' IN content)"
    for name in strategy_names:
        chunks = dict(conn.execute("SELECT kind, count(*) FROM chunk WHERE strategy = %s GROUP BY kind",
                                   [name]).fetchall())
        lo, p10, median, p90, hi = one(
            f"""SELECT min(n), percentile_cont(0.1) WITHIN GROUP (ORDER BY n),
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY n),
                       percentile_cont(0.9) WITHIN GROUP (ORDER BY n), max(n)
                FROM (SELECT {step_len} AS n FROM chunk WHERE strategy = %s AND kind = 'step') s""", [name])
        bins = conn.execute(f"""SELECT ({step_len}) / %s * %s AS edge, count(*) FROM chunk
                                WHERE strategy = %s AND kind = 'step' GROUP BY edge ORDER BY edge""",
                            [STEP_BIN, STEP_BIN, name]).fetchall()
        out["strategies"][name] = {
            "parameters": params.get(name), "chunks": chunks,
            "step_chars": {"min": lo, "p10": p10, "median": median, "p90": p90, "max": hi,
                           "bin_width": STEP_BIN, "bins": {str(edge): n for edge, n in bins}}}
    rows = conn.execute("""SELECT r.id, c.name FROM recipe r JOIN category c ON c.id = r.category_id
                           WHERE r.id = ANY(%s) ORDER BY r.id""", [sorted(set(relevant.values()))]).fetchall()
    out["query_recipe_categories"] = {str(rid): cat for rid, cat in rows}
    out["category_recipes"] = dict(conn.execute("""SELECT c.name, count(*) FROM recipe r
                                                   JOIN category c ON c.id = r.category_id
                                                   GROUP BY c.name ORDER BY count(*) DESC, c.name""").fetchall())
    return out


def write_recipes(conn, run_dir: Path, ranked: dict, relevant: dict[str, int]) -> None:
    """recipes.csv: id, url and title of every Recipe in any ranked list and every query's known Recipe (even one
    no config found), so the report never maps ids itself."""
    ids = sorted({rid for by_key in ranked.values() for top in by_key.values() for rid in top}
                 | set(relevant.values()))
    with open(run_dir / "recipes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["recipe_id", "url", "title"])
        w.writerows(conn.execute("SELECT id, url, title FROM recipe WHERE id = ANY(%s) ORDER BY id", [ids]))


def write_run(run_dir: Path, settings: dict, rows: list[dict], relevant, ranked, timings, kinds,
              right: dict[str, set[int]] | None = None) -> None:
    """`relevant` is the written-from Recipe per query; `right` every right Recipe (default: just that one)."""
    right = right or {qid: {rid} for qid, rid in relevant.items()}
    run_dir.mkdir(parents=True)
    (run_dir / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    (run_dir / "metrics.json").write_text(json.dumps(rows, indent=2) + "\n")

    stage_cols = [f"{st}_{p}" for st in ["total", *STAGES] for p in ("p50_ms", "p95_ms")]
    with open(run_dir / "metrics.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["config", "variant", "strategy", "queries", *metrics.COLUMNS, "short_lists", *stage_cols])
        for r in rows:
            lat = r["latency_ms"]
            w.writerow([r["config"], r["variant"], r["strategy"], r["queries"],
                        *(round(r[m], 4) for m in metrics.COLUMNS), r["short_lists"],
                        *(round(lat[st][p], 2) if st in lat else "" for st in ["total", *STAGES]
                          for p in ("p50_ms", "p95_ms"))])

    with open(run_dir / "per_query.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["config", "variant", "strategy", "query_id", "recipe_id", "rank", "best_kind", "total_ms",
                    *(f"{st}_ms" for st in STAGES), "top_recipe_ids"])
        for v, (c, s, qid), top in sorted_rows(ranked):
            watch = timings[v][c, s, qid]
            w.writerow([c, v, s, qid, relevant[qid], metrics.first_rank(right[qid], top) or "", kinds[v][c, s, qid],
                        round(sum(watch.values()), 2),
                        *(round(watch[st], 2) if st in watch else "" for st in STAGES),
                        " ".join(map(str, top))])

    (run_dir / "table.md").write_text(markdown(rows))


def run(conn, embedder: Embedder, scorer: Scorer | None = None, *, configs: list[str] | None = None,
        strategy_names: list[str] | None = None, query_set: Path = QUERY_SET, limit: int | None = None,
        out: Path = RUNS, arm: str | None = None, arm_scorer: Scorer | None = None,
        qrels: Path | None = None) -> Path:
    """One Evaluation run, or with `arm` an Ablation run (the arm's configs, as default and as arm). Returns its folder.

    An arm that swaps the reranker needs `arm_scorer`, the arm's model loaded by the caller. With `qrels`, each
    query is scored on its first right Recipe; without, on the Recipe it was written from.
    """
    arm_def = {"key": arm, **ARMS[arm]} if arm else None
    if arm_def:
        if configs:
            raise ValueError("an Ablation run takes its configs from the arm; don't pass configs too")
        configs = list(arm_def["configs"])
        if "rerank_model" in arm_def["set"] and arm_scorer is None:
            raise ValueError(f"arm {arm!r} swaps the reranker and needs an arm_scorer")
    configs = configs or list(CONFIGS)
    reranks = any_stage(configs, "rerank")
    if reranks and scorer is None:
        raise ValueError("a Reranking config (hybrid) needs a reranker scorer")
    strategy_names = resolve_strategies(conn, strategy_names)
    if not strategy_names:
        raise ValueError("no Chunking strategy is loaded")
    if arm_def and arm_def["set"].get("dense_index") == "hnsw":
        arm_def["hnsw_indexes"] = hnsw_indexes(conn, strategy_names)
    queries = read_queries(query_set, limit)
    if not queries:
        raise ValueError(f"{query_set} has no queries")
    relevant = {q["query_id"]: q["recipe_id"] for q in queries}
    judged = metrics.read_qrels(qrels) if qrels else {}
    right = {qid: judged.get(qid, set()) | {rid} for qid, rid in relevant.items()}

    started = datetime.now()
    ranked, timings, kinds = search_all(conn, queries, strategy_names, configs, embedder, scorer, arm_def,
                                        arm_scorer, right)
    rows = [row for v in ranked for row in summarize(right, ranked[v], timings[v], v)]

    settings = {
        "started_at": started.isoformat(timespec="seconds"),
        "seconds": round((datetime.now() - started).total_seconds(), 1),
        "git_commit": _git_commit(),
        "configs": configs,
        "strategies": strategy_names,
        "query_set": str(query_set.relative_to(ROOT) if query_set.is_relative_to(ROOT) else query_set),
        "query_set_sha256": hashlib.sha256(query_set.read_bytes()).hexdigest(),
        "qrels": str(qrels.relative_to(ROOT) if qrels.is_relative_to(ROOT) else qrels) if qrels else None,
        "qrels_sha256": hashlib.sha256(qrels.read_bytes()).hexdigest() if qrels else None,
        "queries": len(queries),
        "limit": limit,
        "chunk_pool": POOL,
        "depth": metrics.DEPTH,
        "hybrid_candidates": config.HYBRID_CANDIDATES,
        "rerank_top": config.RERANK_TOP,
        "rrf_k": config.RRF_K,
        "embed_model": config.EMBED_MODEL,
        "rerank_model": config.RERANK_MODEL if reranks else None,
        "warmup_queries": 1,
        "config_order": "rotated",
        "arm": arm_def,
        **_db_settings(conn),
    }
    run_dir = out / started.strftime("%Y%m%d-%H%M%S")
    write_run(run_dir, settings, rows, relevant, ranked, timings, kinds, right)
    write_recipes(conn, run_dir, ranked, relevant)
    (run_dir / "corpus.json").write_text(json.dumps(corpus(conn, strategy_names, relevant), indent=2) + "\n")
    return run_dir


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    picks = p.add_mutually_exclusive_group()
    picks.add_argument("--configs", nargs="+", choices=list(CONFIGS), help="default: all")
    picks.add_argument("--arm", choices=list(ARMS), help="an Ablation run: the arm's configs, as default and as arm")
    p.add_argument("--strategies", nargs="+", help="default: every loaded Chunking strategy")
    p.add_argument("--queries", type=Path, default=QUERY_SET, help="Query set (JSONL)")
    p.add_argument("--qrels", default=str(QRELS), help="pooled qrels CSV, or 'none' for the written-from Recipe only")
    p.add_argument("--limit", type=int, help="only the first N queries, for quick runs")
    p.add_argument("--out", type=Path, default=RUNS, help="parent folder for the run folder")
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    scorer = arm_scorer = None
    if any_stage(ARMS[a.arm]["configs"] if a.arm else a.configs or CONFIGS, "rerank"):
        from api.rerank import Reranker  # imports torch and loads the model, so only when Hybrid runs
        scorer = Reranker().score  # loaded once, before any timing
        if a.arm and (model := ARMS[a.arm]["set"].get("rerank_model")):
            arm_scorer = Reranker(model).score
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn, httpx.Client(timeout=30) as http:
        try:
            run_dir = run(conn, lambda text: embed_query(http, text), scorer, configs=a.configs,
                          strategy_names=a.strategies, query_set=a.queries.resolve(), limit=a.limit, out=a.out,
                          arm=a.arm, arm_scorer=arm_scorer,
                          qrels=None if a.qrels == "none" else Path(a.qrels).resolve())
        except ValueError as e:
            sys.exit(f"evaluate: {e}")
    print((run_dir / "table.md").read_text())
    print(f"Run folder: {run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir}")
