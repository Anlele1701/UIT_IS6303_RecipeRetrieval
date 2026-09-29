# Recipe Retrieval

A searchable store of the Shengtao/recipe dataset that supports two ways of finding recipes from a text query: sparse retrieval and dense retrieval.

## Language

**Recipe**:
One row of the source dataset: a single dish with its title, description, ingredients, directions and metadata.
_Avoid_: Document, record, item

**Chunk**:
A piece of one Recipe's text that is the unit both sparse and dense retrieval rank. Every Chunk belongs to exactly one Recipe and carries that Recipe's title.
_Avoid_: Passage, segment, document

**Summary chunk**:
The Chunk made of a Recipe's title and description.

**Ingredients chunk**:
The single Chunk holding a Recipe's full ingredient list. Ingredients are never split per line.

**Step chunk**:
A Chunk holding a run of consecutive text from a Recipe's directions, in its original order. Where the run starts and ends is the only thing that differs between Chunking strategies; Summary and Ingredients chunks are the same under every Chunking strategy.
_Avoid_: Direction chunk, instruction

**Chunking strategy**:
The named method that turned Recipes into Chunks: fixed-size, sentence-based or semantic, each with its parameters (e.g. 56 tokens per Chunk). A Chunking strategy is built once, offline; changing its parameters means a new name. Chunks from different Chunking strategies can coexist and are never mixed within one search. A Chunking strategy is searchable only once it is loaded: every Recipe has its complete set of Chunks under it.
_Avoid_: Chunker, splitter

**Sparse retrieval**:
Finding recipes by matching query terms against their text, ranked by BM25.
_Avoid_: Keyword search, full-text search, lexical search

**Dense retrieval**:
Finding recipes by comparing the embedding of the query to embeddings of recipe text, ranked by vector similarity.
_Avoid_: Semantic search, vector search, embedding search

**Filter**:
A condition on a Recipe's structured attributes (category, time, rating, nutrition) that narrows the candidates before ranking.
_Avoid_: Facet, constraint

**Hybrid retrieval**:
Finding recipes by running Sparse and Dense retrieval on the same query, merging their two rankings into one by rank position, then Reranking the merged candidates. Reranking is always part of Hybrid retrieval and never applied to Sparse or Dense alone.
_Avoid_: Fusion search, combined search

**Reranking**:
Re-scoring a short list of candidate Chunks by reading the query and each Chunk's text together, and reordering them by that score.
_Avoid_: Re-ranking, second-stage ranking

**Fusion baseline**:
Hybrid retrieval without Reranking: the same merged candidates Hybrid retrieval would rerank, left in rank-position order. Used only in an Evaluation run, to show what Reranking adds. Never served; served Hybrid retrieval always reranks.
_Avoid_: Hybrid RRF, RRF-only search

**Query set**:
The fixed list of test queries in the repo. Each was written from one Recipe. Which Recipes count as right is the Answer key's job, not the Query set's.
_Avoid_: Test set, qrels, benchmark

**Answer key**:
Every judged (query, Recipe) pair, right or not, in `eval/qrels.csv`. A query's right Recipes are the one it was written from plus every Recipe judged as good an answer. The judged Recipes come from pooling the top 5 of every config, Chunking strategy and Ablation arm. A query is scored at the rank of its first right Recipe.
_Avoid_: Ground truth, labels (qrels only as the file name)

**Evaluation run**:
One scoring of the retrieval configs (Sparse, Dense, Fusion baseline, Hybrid) on the Query set under the chosen Chunking strategies, kept as one timestamped folder of settings, metrics and per-query ranks.
_Avoid_: Benchmark, experiment

**Report run**:
The one Evaluation run whose numbers the report states, named explicitly rather than taken as the latest. Ablation runs are compared against it.
_Avoid_: Main run, final run, latest run

**Ablation run**:
An Evaluation run that scores one arm (a single settings change) next to its default, on the same queries in the same run. Its default's ranks must match the Report run's; the arm is compared against that default.
_Avoid_: Experiment, variant run

**Timing repeat**:
An Evaluation run that repeats the Report run's settings only to measure latency. Its ranks must match the Report run's; the report's latency is the median across Timing repeats.
_Avoid_: Benchmark rerun
