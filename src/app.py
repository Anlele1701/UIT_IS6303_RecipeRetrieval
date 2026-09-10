"""
Gradio UI. See docs/05_SYSTEM_ARCHITECTURE.md — Gradio calls the Python
search functions directly, in-process; no separate backend service.

Not run/tested yet (per user request) — this wires the modules together
per the interface defined in docs/06_TECHNICAL_DESIGN.md.
"""

import gradio as gr

from src.config import CONFIG
from src.data.loader import load_subset
from src.data.preprocessing import build_corpus
from src.retrieval.base import SearchResult
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.reranker import HybridRerankRetriever, Reranker

_retrievers: dict[str, object] = {}


def build_retrievers() -> dict[str, object]:
    """
    Loads the subset once and builds all four retrieval methods so the UI
    can switch between them without reloading data/models each time.
    """
    recipes = load_subset(
        split=CONFIG.corpus_split,
        subset_size=CONFIG.subset_size,
        seed=CONFIG.seed,
    )
    corpus = build_corpus(recipes, fields=CONFIG.text_fields)

    bm25 = BM25Retriever(recipes, corpus)
    dense = DenseRetriever(recipes, corpus, model_name=CONFIG.embedding_model_name)
    hybrid = HybridRetriever(bm25, dense, candidate_pool=CONFIG.rerank_candidate_pool)
    reranker = Reranker(model_name=CONFIG.reranker_model_name)
    hybrid_rerank = HybridRerankRetriever(hybrid, reranker, candidate_pool=CONFIG.rerank_candidate_pool)

    return {
        "BM25": bm25,
        "Dense": dense,
        "Hybrid": hybrid,
        "Hybrid + Reranker": hybrid_rerank,
    }


def search(query: str, mode: str, top_k: int):
    if not query:
        return []
    retriever = _retrievers[mode]
    results: list[SearchResult] = retriever.search(query, top_k=int(top_k))
    return [(r.image, f"#{r.rank} · {r.name} (score={r.score:.3f})") for r in results]


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Recipe Image Retrieval") as demo:
        gr.Markdown("# Recipe Image Retrieval\nText query -> top-k recipe images (ANDREEEWW/recipe-with-images)")

        with gr.Row():
            query_box = gr.Textbox(label="Query", placeholder="e.g. quick vegetarian breakfast")
            mode_box = gr.Radio(
                choices=["BM25", "Dense", "Hybrid", "Hybrid + Reranker"],
                value="Hybrid",
                label="Retrieval mode",
            )
            topk_box = gr.Slider(minimum=1, maximum=20, value=CONFIG.default_top_k, step=1, label="Top-k")

        search_button = gr.Button("Search")
        gallery = gr.Gallery(label="Results", columns=5)

        search_button.click(fn=search, inputs=[query_box, mode_box, topk_box], outputs=gallery)

    return demo


if __name__ == "__main__":
    _retrievers = build_retrievers()
    app = build_app()
    app.launch()
