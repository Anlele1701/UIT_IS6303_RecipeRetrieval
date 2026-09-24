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
A Chunk holding a run of consecutive sentences from a Recipe's directions that describe one coherent part of the cooking, in their original order.
_Avoid_: Direction chunk, instruction

**Chunker**:
The named method that turned Recipes into Chunks. Chunks from different Chunkers can coexist and are never mixed within one search.
_Avoid_: Chunking strategy, splitter

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
