"""ParadeDB-backed sparse, dense, and hybrid recipe retrievers."""

from pathlib import Path

import numpy as np

from src.config import CONFIG
from src.db import PROJECT_ROOT, connect
from src.retrieval.base import SearchResult


def _load_image(image_path: str | None):
    if not image_path:
        return None
    from PIL import Image

    path = Path(image_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.is_file():
        return None
    with Image.open(path) as image:
        return image.copy()


def _to_results(rows: list[tuple], load_images: bool = True) -> list[SearchResult]:
    """
    `load_images=False` skips decoding the JPEG for every hit. Evaluation runs
    use it because that disk I/O is larger than the retrieval itself once a
    candidate pool of 100 is fetched per query, and would swamp the latency
    numbers the ablations are meant to compare.
    """
    return [
        SearchResult(
            recipe_idx=int(row[0]),
            rank=rank,
            score=float(row[1]),
            name=row[2],
            image=_load_image(row[3]) if load_images else None,
            text=row[4],
        )
        for rank, row in enumerate(rows, start=1)
    ]


def _get_chunk_profile_id(profile_name: str) -> int:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT profile_id
            FROM retrieval.chunk_profiles
            WHERE profile_name = %s
            """,
            (profile_name,),
        ).fetchone()
    if row is None:
        raise RuntimeError(
            f"Chunk profile {profile_name!r} is not available; "
            "run `npm run data:migrate` first"
        )
    return int(row[0])


class PostgresQueryEncoder:
    def __init__(self, embedding_profile_name: str):
        with connect() as connection:
            row = connection.execute(
                """
                SELECT
                    embedding_profile_id,
                    model_name,
                    dimension,
                    normalize_embeddings,
                    query_prefix
                FROM retrieval.embedding_profiles
                WHERE profile_name = %s
                """,
                (embedding_profile_name,),
            ).fetchone()
        if row is None:
            raise RuntimeError(
                f"Embedding profile {embedding_profile_name!r} is not available; "
                "run `npm run data:migrate` first"
            )

        self.embedding_profile_id = int(row[0])
        self.model_name = row[1]
        self.dimension = int(row[2])
        self.normalize_embeddings = bool(row[3])
        self.query_prefix = row[4]

        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(self.model_name)

    def encode(self, query: str) -> np.ndarray:
        embedding = self.model.encode(
            [f"{self.query_prefix}{query}"],
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )
        vector = np.asarray(embedding[0], dtype="float32")
        if vector.shape != (self.dimension,):
            raise ValueError(
                f"Query encoder produced shape {vector.shape}; "
                f"expected ({self.dimension},)"
            )
        return vector


class PostgresSparseRetriever:
    def __init__(
        self,
        chunk_profile_name: str = CONFIG.chunk_profile_name,
        load_images: bool = True,
    ):
        self.chunk_profile_id = _get_chunk_profile_id(chunk_profile_name)
        self.load_images = load_images

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        if not query.strip():
            return []
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT recipe_idx, score, name, image_path, searchable_text
                FROM retrieval.match_sparse(%s, %s, %s)
                """,
                (query, self.chunk_profile_id, top_k),
            ).fetchall()
        return _to_results(rows, self.load_images)


class PostgresDenseRetriever:
    def __init__(
        self,
        chunk_profile_name: str = CONFIG.chunk_profile_name,
        embedding_profile_name: str = CONFIG.embedding_profile_name,
        encoder: PostgresQueryEncoder | None = None,
        load_images: bool = True,
    ):
        self.chunk_profile_id = _get_chunk_profile_id(chunk_profile_name)
        self.encoder = encoder or PostgresQueryEncoder(embedding_profile_name)
        self.load_images = load_images

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        if not query.strip():
            return []
        query_embedding = self.encoder.encode(query)
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT recipe_idx, score, name, image_path, searchable_text
                FROM retrieval.match_dense(%s, %s, %s, %s)
                """,
                (
                    query_embedding,
                    self.chunk_profile_id,
                    self.encoder.embedding_profile_id,
                    top_k,
                ),
            ).fetchall()
        return _to_results(rows, self.load_images)


class PostgresHybridRetriever:
    """RRF fused inside Postgres by retrieval.match_hybrid (one round trip)."""

    def __init__(
        self,
        chunk_profile_name: str = CONFIG.chunk_profile_name,
        embedding_profile_name: str = CONFIG.embedding_profile_name,
        candidate_pool: int = 100,
        rrf_k: int = 60,
        encoder: PostgresQueryEncoder | None = None,
        load_images: bool = True,
    ):
        self.chunk_profile_id = _get_chunk_profile_id(chunk_profile_name)
        self.encoder = encoder or PostgresQueryEncoder(embedding_profile_name)
        self.candidate_pool = candidate_pool
        self.rrf_k = rrf_k
        self.load_images = load_images

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        if not query.strip():
            return []
        query_embedding = self.encoder.encode(query)
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT recipe_idx, score, name, image_path, searchable_text
                FROM retrieval.match_hybrid(%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    query,
                    query_embedding,
                    self.chunk_profile_id,
                    self.encoder.embedding_profile_id,
                    top_k,
                    self.candidate_pool,
                    self.rrf_k,
                ),
            ).fetchall()
        return _to_results(rows, self.load_images)


class PythonRRFHybridRetriever:
    """
    Same fusion as PostgresHybridRetriever, but the two candidate lists are
    pulled separately and merged in the service layer.

    This is the "where does the logic live" ablation from
    docs/10_ABLATION_STUDY.md: identical ranking, but two round trips and the
    full candidate rows crossing the wire instead of only the final top-k.
    """

    def __init__(
        self,
        chunk_profile_name: str = CONFIG.chunk_profile_name,
        embedding_profile_name: str = CONFIG.embedding_profile_name,
        candidate_pool: int = 100,
        rrf_k: int = 60,
        encoder: PostgresQueryEncoder | None = None,
        load_images: bool = True,
    ):
        encoder = encoder or PostgresQueryEncoder(embedding_profile_name)
        self.sparse = PostgresSparseRetriever(chunk_profile_name, load_images=load_images)
        self.dense = PostgresDenseRetriever(
            chunk_profile_name,
            embedding_profile_name,
            encoder=encoder,
            load_images=load_images,
        )
        self.encoder = encoder
        self.candidate_pool = candidate_pool
        self.rrf_k = rrf_k
        self.load_images = load_images

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        from src.retrieval.hybrid import reciprocal_rank_fusion

        if not query.strip():
            return []
        sparse_results = self.sparse.search(query, top_k=self.candidate_pool)
        dense_results = self.dense.search(query, top_k=self.candidate_pool)

        by_idx = {r.recipe_idx: r for r in sparse_results + dense_results}
        fused = reciprocal_rank_fusion(
            [sparse_results, dense_results],
            k=self.rrf_k,
        )[:top_k]

        results = []
        for rank, (recipe_idx, score) in enumerate(fused, start=1):
            base = by_idx[recipe_idx]
            results.append(
                SearchResult(
                    recipe_idx=recipe_idx,
                    rank=rank,
                    score=score,
                    name=base.name,
                    image=base.image,
                    text=base.text,
                )
            )
        return results
