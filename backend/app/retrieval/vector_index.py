"""
Vector index for semantic similarity over stored fact embeddings.
Brute-force cosine similarity in Python — fast enough at this scale
(hundreds to low thousands of facts). No FAISS, no external vector DB.
Upgrade path documented in README.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.app.canonicalization.embedder import cosine_similarity, embed_text
from backend.app.config import DB_PATH
from backend.app.models.schema import Fact
from backend.app.storage.repository import list_all_facts_with_embeddings


class VectorIndex:
    def __init__(self) -> None:
        self._facts: list[Fact] = []
        self._embeddings: np.ndarray | None = None  # shape (N, D)

    def build(self, db_path: Path = DB_PATH) -> None:
        """Load all facts with embeddings from DB."""
        all_pairs = list_all_facts_with_embeddings(db_path)
        facts_with_emb = [(f, e) for f, e in all_pairs if e is not None]
        if not facts_with_emb:
            self._facts = []
            self._embeddings = None
            return
        self._facts = [f for f, _ in facts_with_emb]
        self._embeddings = np.stack([e for _, e in facts_with_emb])

    def query(self, query_text: str, top_k: int = 20) -> list[tuple[Fact, float]]:
        """Return top-k facts by cosine similarity to query_text."""
        if self._embeddings is None or len(self._facts) == 0:
            return []
        q_emb = embed_text(query_text)
        # Brute-force dot product (embeddings are normalized → cosine sim)
        scores = self._embeddings @ q_emb  # shape (N,)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self._facts[i], float(scores[i])) for i in top_indices if scores[i] > 0]
