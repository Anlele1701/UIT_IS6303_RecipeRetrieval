import type { Method } from './api'

/** Column order: Hybrid sits between the two methods it is built from. */
export const COLUMN_ORDER: Method[] = ['sparse', 'hybrid', 'dense']

// Full class names so Tailwind can find them in the source.
export const METHOD: Record<Method, {
  name: string
  blurb: string
  scoreName: string
  text: string
  bg: string
  border: string
  ring: string
  stroke: string
  fill: string
}> = {
  sparse: {
    name: 'Sparse',
    blurb: 'Matches the words in the query and ranks Chunks by BM25.',
    scoreName: 'BM25 score',
    text: 'text-sparse', bg: 'bg-sparse', border: 'border-sparse', ring: 'ring-sparse',
    stroke: 'stroke-sparse', fill: 'fill-sparse',
  },
  hybrid: {
    name: 'Hybrid',
    blurb: 'Merges the Sparse and Dense rankings, then reranks the top candidates with a cross-encoder.',
    scoreName: 'Rerank score',
    text: 'text-hybrid', bg: 'bg-hybrid', border: 'border-hybrid', ring: 'ring-hybrid',
    stroke: 'stroke-hybrid', fill: 'fill-hybrid',
  },
  dense: {
    name: 'Dense',
    blurb: 'Compares the meaning of the query and each Chunk using embeddings.',
    scoreName: 'Cosine similarity',
    text: 'text-dense', bg: 'bg-dense', border: 'border-dense', ring: 'ring-dense',
    stroke: 'stroke-dense', fill: 'fill-dense',
  },
}
