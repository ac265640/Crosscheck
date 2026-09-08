"""
Local sentence-transformer embedding wrapper.
Uses BAAI/bge-small-en-v1.5 on CPU — no API key, no extra cost.
Embedding dimension: 384.
"""

from __future__ import annotations

import threading
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from backend.app.config import EMBEDDING_MODEL

# Singleton — load once, reuse with thread safety
_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    _model = SentenceTransformer(EMBEDDING_MODEL, device="cpu", local_files_only=True)
                except Exception:
                    _model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    return _model


def embed_text(text: str) -> np.ndarray:
    """Embed a single text string. Returns float32 numpy array."""
    model = get_embedder()
    with torch.no_grad():
        embedding = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
    return embedding.astype(np.float32)


def embed_batch(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts. Returns shape (N, D) float32 array."""
    if not texts:
        return np.empty((0, 384), dtype=np.float32)
    model = get_embedder()
    with torch.no_grad():
        embeddings = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
    return embeddings.astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors."""
    # Since embeddings are already normalized, dot product = cosine similarity
    return float(np.dot(a, b))
