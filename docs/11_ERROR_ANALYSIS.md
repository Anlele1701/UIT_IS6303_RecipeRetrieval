# 11 — Error Analysis

Cases are selected automatically from the saved per-query records by
`python -m src.evaluation.error_analysis`, which writes
`experiments/error_cases.md`. That file holds the raw cards; this document
holds the interpretation. Configurations compared: `bm25`, `dense`,
`hybrid_rrf`, `hybrid_rerank`, all at Recall@10.

## How often each pattern occurs

| pattern | queries (of 300) |
|---|---|
| BM25 retrieves it, dense does not | 109 |
| The cross-encoder demotes a correct hit | 10 |
| Dense retrieves it, BM25 does not | 2 |
| No configuration retrieves the labelled recipe | 1 |
| RRF drops a hit that both inputs had | 0 |

Two things stand out. Dense retrieval almost never contributes something
BM25 missed (2 queries), which is why fusion cannot pay for itself on this
query set. And RRF never loses a document that both inputs found — fusion is
safe in terms of recall, it only damages the ordering, which is what the
reranker then repairs.

## Misses by query family

| config | name_kw | ingredient_combo | desc_short | synonym_hard |
|---|---|---|---|---|
| `bm25` | 2/75 | 0/75 | 0/75 | 4/75 |
| `dense` | 1/75 | 29/75 | 48/75 | 35/75 |
| `hybrid_rrf` | 0/75 | 11/75 | 8/75 | 21/75 |
| `hybrid_rerank` | 0/75 | 0/75 | 1/75 | 1/75 |

Dense fails on exactly the families whose source field is a minority of the
combined chunk (`desc_short`, and any 4 ingredients out of a full list); it
is at parity with BM25 on `name_kw`, where the source field is short and
distinctive enough to survive pooling.

## Good case — dense recovering a lexically crowded query

```text
Query (name_kw): "sugar cookies"
Labelled recipe: #4241 Sugar Cookies VI
Ranks: bm25 #24, dense #7, hybrid_rrf #9, hybrid_rerank #5
BM25 top-5: Cookie Mold Sugar Cookies / Irish Shamrock Cookies /
            Becky's Sugary Sugar Cookies / Rum Raisin Cookies /
            Tender Crisp Sugar Cookies
```

This is the one query type where the dense encoder is genuinely useful. The
corpus contains dozens of near-identical sugar cookie recipes, so BM25 has no
lexical signal left to separate them and ranks by term statistics alone. The
embedding places the plainest recipe closest to the plainest query.

It is also the clearest example of a **labelling gap**, not a retrieval
failure: every one of BM25's top-5 is a sugar cookie recipe and would satisfy
a real user, but only #4241 counts as correct. Counting this as an error is
an artefact of one-relevant-document-per-query labelling
(`08_EVALUATION.md`), and some fraction of the 109 "BM25 wins" and the
`name_kw` misses are the same artefact.

## Bad case — synonym substitution defeating the whole pipeline

```text
Query (synonym_hard): "digestive biscuits, pecans, sour cream, cream cheese"
Rewritten from:       "graham crackers, pecans, sour cream, cream cheese"
                      (graham -> digestive, crackers -> biscuits)
Labelled recipe: #1204 Perfect Cheesecake Everytime
Ranks: bm25 #45, dense miss, hybrid_rrf miss, hybrid_rerank miss
BM25 top-5: Sour Cream Raisin Pie VI / Chocolate peanut butter cheesecake /
            Grape and Coconut Salad / White Chocolate Fudge with Pecans /
            Easy Cheddar Biscuits with Fresh Herbs
```

The only query in the set that every configuration misses. After the
substitution the query keeps just two terms that appear in the document
(`pecans`, `sour cream`) and both are common, so BM25 has nothing rare to
anchor on and drifts to recipes matching one term each. "Digestive biscuits"
actively misleads it towards `Easy Cheddar Biscuits`. Dense retrieval should
have handled this — it is precisely a vocabulary-mismatch case — but the
cheesecake's pooled embedding covers its whole ingredient list, so a
four-ingredient query is matched against a vector that is mostly about
everything else in the recipe.

This one query contains both failure modes at once, and shows they compound:
the lexical stage fails on vocabulary, the semantic stage fails on pooling
dilution, and fusion cannot recover what neither input found.

## Bad case — the reranker demoting a correct hit

```text
Query (synonym_hard): "apples, sultanas, walnuts, icing sugar"
Rewritten from:       "apples, raisins, walnuts, confectioners sugar"
Labelled recipe: #2361 Apple Hermits
Ranks: bm25 #13, dense #5, hybrid_rrf #3, hybrid_rerank #8
```

Fusion had this at rank 3 and the cross-encoder pushed it to 8 — one of 10
such queries. The reranker scores `(query, full recipe text)` pairs, and the
recipe text still says "raisins" and "confectioners' sugar" while the query
says "sultanas" and "icing sugar". A cross-encoder trained on MS MARCO web
passages has no particular reason to know these are the same ingredients, so
it reads the pair as a partial match and scores it below recipes that repeat
the query's surface words. Net effect across the query set is still strongly
positive (MRR 0.679 to 0.934), but the reranker inherits the vocabulary
problem rather than solving it.

## Error categories specific to `recipe-with-images`

Confirmed by the runs above:

- **Pooling dilution** — the dominant dense failure. One embedding for
  `name + ingredients + description` is dominated by the longest field, so a
  query derived from a short field matches poorly. Fixed by `field_chunk_v1`
  (Ablation E). Note this is *not* truncation: only 1.5% of combined chunks
  exceed the encoder's 256-token window.
- **Synonym mismatch** — US/UK ingredient naming (shrimp/prawns,
  cilantro/coriander, graham cracker/digestive biscuit). Hurts BM25 and the
  cross-encoder; would be the main argument for a stronger dense stage.
- **Labelling gaps** — one relevant recipe per query in a corpus with many
  interchangeable recipes of the same dish. Inflates the apparent error rate
  of every configuration, most visibly on `name_kw`.
- **Rare ingredient as a unique key** — the flip side: in a 5000-recipe
  corpus a single rare term ("amaretto liqueur", "beef consomme") identifies
  a recipe outright, which is why BM25 is so hard to beat here and why these
  results should not be extrapolated to a corpus that is orders of magnitude
  larger.
- **Ingredients field noise** — quantities, units and sub-headers
  ("Dressing:", "For serving:") dilute both lexical and embedding signal;
  handled at query-construction time but still present in the documents.
- **Visually similar but semantically different dish** — not observable
  here: retrieval is text-only and images are display-only.
