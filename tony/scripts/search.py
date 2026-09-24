# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2", "numpy>=1.26"]
# ///
"""Query the chunk table with sparse (BM25) or dense (vector) retrieval.

    uv run scripts/search.py bm25   "creamy mushroom rice"
    uv run scripts/search.py vector "something warm for a rainy day" --category soups-stews-and-chili
    uv run scripts/search.py bm25   "chicken" --category salad --max-minutes 30 --kind ingredients
"""

import argparse
import os

import psycopg

from ingest import CHUNKER, DATABASE_URL, embed, to_pgvector

FILTERS = {  # CLI flag -> SQL condition on chunk
    "category": "category = %s",
    "kind": "kind = %s",
    "max_minutes": "total_minutes <= %s",
    "min_rating": "rating >= %s",
    "max_calories": "calories <= %s",
    "min_protein": "protein_g >= %s",
}


def search(conn, method: str, query: str, k: int = 10, **filters):
    where, params = ["chunker = %s"], [CHUNKER]
    for name, value in filters.items():
        if value is not None:
            where.append(FILTERS[name])
            params.append(value)

    if method == "bm25":
        sql = f"""SELECT id, recipe_id, kind, position, pdb.score(id) AS score, content
                  FROM chunk WHERE content ||| %s AND {' AND '.join(where)}
                  ORDER BY score DESC LIMIT %s"""
        params = [query, *params, k]
    else:
        qvec = to_pgvector(embed([f"search_query: {query}"])[0])
        sql = f"""SELECT id, recipe_id, kind, position,
                         1 - (embedding <=> %s::vector) AS score, content
                  FROM chunk WHERE id @@@ pdb.all() AND {' AND '.join(where)}
                  ORDER BY embedding <=> %s::vector LIMIT %s"""
        params = [qvec, *params, qvec, k]
    return conn.execute(sql, params).fetchall()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("method", choices=["bm25", "vector"])
    p.add_argument("query")
    p.add_argument("-k", type=int, default=10)
    p.add_argument("--category")
    p.add_argument("--kind", choices=["summary", "ingredients", "step"])
    p.add_argument("--max-minutes", type=int)
    p.add_argument("--min-rating", type=float)
    p.add_argument("--max-calories", type=float)
    p.add_argument("--min-protein", type=float)
    a = p.parse_args()

    with psycopg.connect(os.environ.get("DATABASE_URL", DATABASE_URL)) as conn:
        rows = search(conn, a.method, a.query, a.k, category=a.category, kind=a.kind,
                      max_minutes=a.max_minutes, min_rating=a.min_rating,
                      max_calories=a.max_calories, min_protein=a.min_protein)
    for i, (cid, rid, kind, pos, score, content) in enumerate(rows, 1):
        title, _, body = content.partition("\n")
        print(f"{i:>2}. {score:7.3f}  [{kind}{'#' + str(pos) if kind == 'step' else ''}] "
              f"{title}  (recipe {rid})\n    {body[:140]}")
