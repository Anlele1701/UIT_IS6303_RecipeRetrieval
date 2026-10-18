"""Report check: do cosine, inner product and L2 rank Chunks the same way for A3's embeddings?

    uv run scripts/similarity_check.py      # -> eval/similarity_check.json

For unit-length vectors, ||q - d||^2 = 2 - 2 q.d and cos(q, d) = q.d, so all three must give the same order.
This measures it on the stored Chunk embeddings (vector norms) and on N seeded A1 queries (exact top-50 by each
operator over a plain scan of chunk_semantic, no ANN index), to support the design rationale in the report.
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from api import config  # noqa: E402
from api.embed import embed_query  # noqa: E402

OUT = ROOT / "eval" / "similarity_check.json"
SEED, N, K = 42, 20, 50
OPS = {"cosine": "<=>", "inner_product": "<#>", "l2": "<->"}


def main():
    queries = [json.loads(l)["text"] for l in (ROOT / "eval" / "queries.jsonl").read_text(encoding="utf-8").splitlines()]
    sample = random.Random(SEED).sample(queries, N)
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=60) as http:
        norms = conn.execute("SELECT min(vector_norm(embedding)), max(vector_norm(embedding)), count(*) "
                             "FROM chunk_semantic").fetchone()
        same = {op: 0 for op in OPS if op != "cosine"}
        for q in sample:
            v = embed_query(http, q)
            ranked = {op: [r[0] for r in conn.execute(
                f"SELECT id FROM (SELECT id, embedding FROM chunk_semantic OFFSET 0) x "
                f"ORDER BY embedding {sym} %s::vector, id LIMIT {K}", [v])] for op, sym in OPS.items()}
            for op in same:
                same[op] += ranked[op] == ranked["cosine"]
    res = {"seed": SEED, "queries": N, "top_k": K, "chunks": norms[2],
           "embedding_norm": {"min": round(norms[0], 6), "max": round(norms[1], 6)},
           "identical_top_k_vs_cosine": {op: f"{n}/{N}" for op, n in same.items()}}
    OUT.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
