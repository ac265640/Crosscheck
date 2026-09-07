"""
Unit tests for the canonicalization embedder and similarity logic.
Tests the local embedding model without LLM calls.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.canonicalization.embedder import cosine_similarity, embed_text


class TestEmbedder:
    def test_embed_text_returns_numpy_array(self):
        emb = embed_text("Delhivery revenue from services")
        assert isinstance(emb, np.ndarray)
        assert emb.ndim == 1
        assert emb.shape[0] > 0

    def test_embed_text_is_normalized(self):
        emb = embed_text("test sentence for normalization")
        norm = float(np.linalg.norm(emb))
        assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"

    def test_same_text_same_embedding(self):
        text = "GDP growth rate of India"
        emb1 = embed_text(text)
        emb2 = embed_text(text)
        np.testing.assert_array_almost_equal(emb1, emb2, decimal=5)

    def test_similar_texts_have_high_similarity(self):
        emb_a = embed_text("Delhivery revenue from services FY24")
        emb_b = embed_text("Delhivery service revenue fiscal year 2024")
        sim = cosine_similarity(emb_a, emb_b)
        assert sim > 0.70, f"Expected high similarity, got {sim:.3f}"

    def test_dissimilar_texts_have_lower_similarity(self):
        emb_a = embed_text("Delhivery revenue from services")
        emb_b = embed_text("India current account deficit percent GDP")
        sim = cosine_similarity(emb_a, emb_b)
        assert sim < 0.85, f"Expected lower similarity, got {sim:.3f}"

    def test_cosine_similarity_symmetric(self):
        emb_a = embed_text("fact about revenue")
        emb_b = embed_text("revenue related fact")
        sim_ab = cosine_similarity(emb_a, emb_b)
        sim_ba = cosine_similarity(emb_b, emb_a)
        assert abs(sim_ab - sim_ba) < 1e-6

    def test_identical_embeddings_similarity_is_one(self):
        emb = embed_text("unique test phrase for identity check")
        sim = cosine_similarity(emb, emb)
        assert abs(sim - 1.0) < 1e-5
