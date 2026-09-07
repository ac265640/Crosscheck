"""
BM25 index over fact sentences.
Builds in-memory index from stored facts; rebuilt on each query for simplicity
(at this scale, rebuilding is fast enough — document this trade-off in README).
"""

from __future__ import annotations

import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from backend.app.config import DB_PATH
from backend.app.models.schema import Fact
from backend.app.storage.repository import list_all_facts_with_embeddings


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\b\w+\b", text.lower())


def _fact_to_sentence(fact: Fact) -> str:
    """Build a synthetic 'fact sentence' for indexing."""
    scope_str = " ".join(f"{k}:{v}" for k, v in fact.scope.items())
    unit_str = fact.unit or ""
    return f"{fact.entity} {fact.attribute}: {fact.value} {unit_str} {scope_str}".strip()


class BM25Index:
    def __init__(self) -> None:
        self._facts: list[Fact] = []
        self._index: BM25Okapi | None = None

    def build(self, db_path: Path = DB_PATH) -> None:
        """Load all facts from DB and build the BM25 index."""
        all_pairs = list_all_facts_with_embeddings(db_path)
        self._facts = [f for f, _ in all_pairs]
        if not self._facts:
            self._index = None
            return
        corpus = [_tokenize(_fact_to_sentence(f)) for f in self._facts]
        self._index = BM25Okapi(corpus)

    def query(self, query_text: str, top_k: int = 20) -> list[tuple[Fact, float]]:
        """Return top-k facts by BM25 score."""
        if self._index is None or not self._facts:
            return []
        tokens = _tokenize(query_text)
        scores = self._index.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(self._facts[i], float(s)) for i, s in ranked[:top_k] if s > 0]
