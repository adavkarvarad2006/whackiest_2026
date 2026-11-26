"""Sentence Transformers embedding service (all-MiniLM-L6-v2, 384-dim)."""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from typing import Sequence

from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    settings = get_settings()
    logger.info("Loading SentenceTransformer model: %s", settings.embedding_model_name)
    return SentenceTransformer(settings.embedding_model_name)


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def _embed_single_long_text(model: SentenceTransformer, text: str) -> list[float]:
    """
    Embed a chunk (800-1000 tokens) without truncating tail content under MiniLM's 256-token window.
    Splits into overlapping ~180-word windows and mean-pools normalized embeddings.
    """
    words = text.split()
    if len(words) <= 180:
        vec = model.encode(text, normalize_embeddings=True).tolist()
        return [float(x) for x in vec]

    windows = []
    step = 140
    for start in range(0, len(words), step):
        window_text = " ".join(words[start : start + 180])
        if window_text:
            windows.append(window_text)
        if start + 180 >= len(words):
            break

    vecs = model.encode(windows, normalize_embeddings=True)
    dim = len(vecs[0])
    pooled = [0.0] * dim
    for v in vecs:
        for i in range(dim):
            pooled[i] += float(v[i])
    return _normalize(pooled)


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Generate 384-dim L2-normalized embeddings for document chunks."""
    if not texts:
        return []
    model = _load_model()
    return [_embed_single_long_text(model, t) for t in texts]


def embed_query(query: str) -> list[float]:
    """Generate a 384-dim L2-normalized embedding for a user query."""
    model = _load_model()
    vec = model.encode(query.strip(), normalize_embeddings=True).tolist()
    return [float(x) for x in vec]
