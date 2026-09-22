"""
Gradio UI. See docs/05_SYSTEM_ARCHITECTURE.md — Gradio calls the Python
search functions directly, in-process; no separate backend service.

Run `npm run data:migrate` before starting the app so ParadeDB contains
the configured corpus, chunks, and embeddings.
"""

import gradio as gr

from src.config import CONFIG
from src.retrieval.base import SearchResult
from src.retrieval.postgres import (
    PostgresDenseRetriever,
    PostgresHybridRetriever,
    PostgresQueryEncoder,
    PostgresSparseRetriever,
)
from src.retrieval.reranker import HybridRerankRetriever, Reranker

_retrievers: dict[str, object] = {}


def build_retrievers() -> dict[str, object]:
    """
    Connects all four modes to the same versioned corpus in ParadeDB.
    Dense and hybrid share one query encoder instance.
    """
    encoder = PostgresQueryEncoder(CONFIG.embedding_profile_name)
    sparse = PostgresSparseRetriever(CONFIG.chunk_profile_name)
    dense = PostgresDenseRetriever(
        CONFIG.chunk_profile_name,
        CONFIG.embedding_profile_name,
        encoder=encoder,
    )
    hybrid = PostgresHybridRetriever(
        CONFIG.chunk_profile_name,
        CONFIG.embedding_profile_name,
        candidate_pool=CONFIG.rerank_candidate_pool,
        encoder=encoder,
    )
    reranker = Reranker(model_name=CONFIG.reranker_model_name)
    hybrid_rerank = HybridRerankRetriever(hybrid, reranker, candidate_pool=CONFIG.rerank_candidate_pool)

    return {
        "BM25": sparse,
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
