"""Batch embedding generation using sentence-transformers/all-MiniLM-L6-v2 (384-dim)."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def generate_embeddings(texts: Sequence[str], batch_size: int = 64) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    vecs = model.encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [[float(x) for x in row] for row in vecs]


def embed_single_query(query: str) -> list[float]:
    model = get_embedding_model()
    vec = model.encode(query.strip(), normalize_embeddings=True, show_progress_bar=False)
    return [float(x) for x in vec]
