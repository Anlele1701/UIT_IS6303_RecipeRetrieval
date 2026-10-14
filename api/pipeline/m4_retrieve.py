"""M4 retrieval with hard filters (A3_ke_hoach_build.md 6.3), on the strategy's partition (ADR-0005 (a)).

BM25 and Dense run on chunk_<strategy> with the constraints as WHERE conditions inside the ParadeDB index,
then RRF as in A1 (api/retrieval.rrf). The flags choose how constraints apply, with everything else equal:
  filter + norm   definite tags: NOT (allergens @@@ pdb.term_set(..)), NOT (ingredients_norm @@@ ..), diet_flags ..
  filter, no norm S-Norm: ILIKE on the raw ingredient lines (no canonical ingredients, no tags)
  no filter       S-Filter: the constraints are written into the query text instead ([S12])
Possible ("có thể chứa") tags never filter (Thy, M1). ingredients_include is only a soft signal in the text.
"""

from collections.abc import Callable

import psycopg
from psycopg import sql

from .. import config
from ..retrieval import Candidate, rrf
from .schemas import Constraints

POOL = 50  # Chunks per retriever, as A1's hybrid_candidates
COLUMNS = sql.SQL("id, recipe_id, kind, position, content")

# S-Norm: plain words for raw-line ILIKE (what a system without the lexicon could do)
NAIVE_ALLERGEN = {
    "milk": ["milk", "butter", "cheese", "cream", "yogurt"], "egg": ["egg"], "fish": ["fish", "salmon", "tuna", "anchov"],
    "crustacean_shellfish": ["shrimp", "prawn", "crab", "lobster"],
    "tree_nuts": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut"], "peanut": ["peanut"],
    "wheat": ["flour", "wheat", "bread", "pasta"], "soy": ["soy", "tofu"], "sesame": ["sesame", "tahini"],
}
NAIVE_DIET = {
    "vegetarian": ["beef", "pork", "chicken", "turkey", "bacon", "ham", "sausage", "fish", "shrimp", "lamb", "gelatin"],
    "vegan": ["beef", "pork", "chicken", "turkey", "bacon", "ham", "sausage", "fish", "shrimp", "lamb", "gelatin",
              "milk", "butter", "cheese", "cream", "egg", "honey", "yogurt"],
}


def conditions(c: Constraints, norm: bool, unknown_strict: bool) -> tuple[sql.Composable, list]:
    """WHERE conditions (joined with AND) for one partition, and their parameters."""
    parts: list[sql.Composable] = []
    params: list = []
    if norm:
        if c.allergens_exclude:
            parts.append(sql.SQL("NOT (allergens @@@ pdb.term_set(%s::text[]))"))
            params.append(c.allergens_exclude)
            if unknown_strict:
                parts.append(sql.SQL("has_unknown = false"))
        if c.ingredients_exclude:
            parts.append(sql.SQL("NOT (ingredients_norm @@@ pdb.term_set(%s::text[]))"))
            params.append(c.ingredients_exclude)
        if c.diet:
            parts.append(sql.SQL("diet_flags @@@ pdb.term_set(%s::text[])"))
            params.append([c.diet])
    else:
        words = [w for a in c.allergens_exclude for w in NAIVE_ALLERGEN[a]] + list(c.ingredients_exclude)
        words += NAIVE_DIET.get(c.diet or "", [])
        if words:
            parts.append(sql.SQL("NOT EXISTS (SELECT 1 FROM recipe_ingredient ri WHERE ri.recipe_id = {t}.recipe_id "
                                 "AND ri.line ILIKE ANY(%s))").format(t=sql.Identifier("x")))
            params.append([f"%{w}%" for w in dict.fromkeys(words)])
    if c.max_total_minutes:
        parts.append(sql.SQL("total_minutes <= %s"))
        params.append(c.max_total_minutes)
    if c.max_calories:
        parts.append(sql.SQL("calories <= %s"))
        params.append(c.max_calories)
    if c.category:
        parts.append(sql.SQL("category = %s"))
        params.append(c.category)
    return (sql.SQL(" AND ").join(parts) if parts else sql.SQL("true")), params


def constraints_as_text(c: Constraints) -> str:
    """S-Filter: what the user asked for, appended to the query (the embedding has to cope with the negation)."""
    bits = [f"without {a.replace('_', ' ')}" for a in c.allergens_exclude]
    bits += [f"without {i}" for i in c.ingredients_exclude]
    bits += [c.diet] if c.diet else []
    bits += [f"ready in {c.max_total_minutes} minutes"] if c.max_total_minutes else []
    return ", ".join(bits)


def query_text(query: str, c: Constraints, filter_on: bool) -> str:
    extra = [", ".join(c.ingredients_include)] if c.ingredients_include else []  # soft signal (6.3)
    if not filter_on:
        extra.append(constraints_as_text(c))
    return " ".join([query, *[e for e in extra if e]]).strip()


def search(conn: psycopg.Connection, text: str, qvec: str, c: Constraints, *, filter_on: bool, norm: bool,
           unknown_strict: bool = False, strategy: str = config.CHAT_STRATEGY, watch=None,
           pool: int = POOL) -> list[Candidate]:
    """RRF-fused Chunks (best first), up to rerank_top, honouring the constraints when filter_on."""
    table = sql.Identifier(f"chunk_{strategy}")
    cond, params = conditions(c, norm, unknown_strict) if filter_on else (sql.SQL("true"), [])
    timed = watch or (lambda stage: _null())
    with timed("sparse"):
        sparse = _rows(conn, sql.SQL("SELECT {cols}, pdb.score(id) AS score FROM {t} AS x WHERE content ||| %s AND {cond} "
                                     "ORDER BY score DESC, id LIMIT %s").format(cols=COLUMNS, t=table, cond=cond),
                       [text, *params, pool])
    with timed("dense"):
        dense = _rows(conn, sql.SQL("SELECT {cols}, 1 - (embedding <=> %s::vector) AS score FROM {t} AS x "
                                    "WHERE id @@@ pdb.all() AND {cond} ORDER BY embedding <=> %s::vector LIMIT %s").format(
            cols=COLUMNS, t=table, cond=cond), [qvec, *params, qvec, pool])
    with timed("rrf"):
        return rrf(sparse, dense)[:config.RERANK_TOP]


def _rows(conn, query, params) -> list[Candidate]:
    return [Candidate(*r) for r in conn.execute(query, params).fetchall()]


class _null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


Embedder = Callable[[str], str]
