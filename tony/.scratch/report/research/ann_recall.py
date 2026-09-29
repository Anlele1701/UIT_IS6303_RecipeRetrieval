import json, sys, time, statistics as st
from pathlib import Path
ROOT = Path.cwd(); sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"scripts"))
import httpx, psycopg
from api import config, retrieval
from api.embed import embed_query
from api.filters import SearchParams
import metrics
PROBES = [0.02, 0.05, 0.2, 1.0]
qs = [json.loads(l) for l in open("eval/queries.jsonl")]
with httpx.Client(timeout=60) as h:
    vecs = {q["query_id"]: embed_query(h, q["text"]) for q in qs}
res = {}
with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
    for strat in ["fixed", "semantic", "sentence"]:
        out = {p: {"ids": {}, "ms": []} for p in PROBES}
        for p in PROBES:
            conn.execute(f"SET paradedb.vector_cluster_max_probe = {p}")
            retrieval.dense(conn, SearchParams(q="x", strategy=strat, k=5), vecs[qs[0]["query_id"]], 100)  # warmup
            for q in qs:
                t = time.perf_counter()
                hits = retrieval.dense(conn, SearchParams(q=q["text"], strategy=strat, k=5), vecs[q["query_id"]], 100)
                out[p]["ms"].append((time.perf_counter() - t) * 1000)
                out[p]["ids"][q["query_id"]] = hits
        conn.execute("RESET paradedb.vector_cluster_max_probe")
        ex = out[1.0]["ids"]
        for p in PROBES:
            r100, r50, ranks, lost, gained = [], [], [], 0, 0
            for q in qs:
                a = out[p]["ids"][q["query_id"]]; e = ex[q["query_id"]]
                es100 = {c.chunk_id for c in e}; es50 = {c.chunk_id for c in e[:50]}
                r100.append(len({c.chunk_id for c in a} & es100) / max(1, len(es100)))
                r50.append(len({c.chunk_id for c in a[:50]} & es50) / max(1, len(es50)))
                ra = metrics.rank_of(q["recipe_id"], [c.recipe_id for c in a])
                re_ = metrics.rank_of(q["recipe_id"], [c.recipe_id for c in e])
                ranks.append(ra)
                if re_ and not ra: lost += 1
                if ra and not re_: gained += 1
            n = len(qs)
            res[(strat, p)] = dict(
                chunk_recall100=round(st.mean(r100), 3), min100=round(min(r100), 2),
                chunk_recall50=round(st.mean(r50), 3),
                R5=round(sum(1 for r in ranks if r and r <= 5) / n, 3),
                R20=round(sum(1 for r in ranks if r) / n, 3),
                MRR=round(sum(1 / r for r in ranks if r) / n, 3),
                lost_vs_exact=lost, gained_vs_exact=gained,
                p50_ms=round(st.median(out[p]["ms"]), 1),
                p95_ms=round(sorted(out[p]["ms"])[int(0.95 * n)], 1))
            print(strat, p, res[(strat, p)], flush=True)
