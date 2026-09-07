"""
Hybrid retriever combining BM25 + vector search via Reciprocal Rank Fusion.
Used to find candidate facts to compare against a given fact.
Primary lookup: exact canonical_key match. Secondary: hybrid for near-misses.
"""

from __future__ import annotations

from pathlib import Path

from backend.app.config import DB_PATH
from backend.app.models.schema import Fact
from backend.app.retrieval.bm25_index import BM25Index, _fact_to_sentence
from backend.app.retrieval.vector_index import VectorIndex
from backend.app.storage.repository import list_all_facts_with_embeddings, list_facts_for_canonical_key


def reciprocal_rank_fusion(
    bm25_results: list[tuple[Fact, float]],
    vector_results: list[tuple[Fact, float]],
    k: int = 60,
) -> list[tuple[Fact, float]]:
    """
    Combine BM25 and vector rankings using Reciprocal Rank Fusion.
    RRF score = sum(1 / (k + rank)) for each result list.
    """
    rrf_scores: dict[str, float] = {}
    fact_map: dict[str, Fact] = {}

    for rank, (fact, _) in enumerate(bm25_results, start=1):
        rrf_scores[fact.id] = rrf_scores.get(fact.id, 0.0) + 1.0 / (k + rank)
        fact_map[fact.id] = fact

    for rank, (fact, _) in enumerate(vector_results, start=1):
        rrf_scores[fact.id] = rrf_scores.get(fact.id, 0.0) + 1.0 / (k + rank)
        fact_map[fact.id] = fact

    sorted_ids = sorted(rrf_scores.keys(), key=lambda fid: rrf_scores[fid], reverse=True)
    return [(fact_map[fid], rrf_scores[fid]) for fid in sorted_ids]


def find_candidate_facts(
    query_fact: Fact,
    db_path: Path = DB_PATH,
    top_k: int = 20,
    exclude_document_id: str | None = None,
) -> list[Fact]:
    """
    Find candidate facts to compare against query_fact.
    
    Strategy:
    1. First: get all facts with the same canonical_key (cheap, exact match)
    2. Additionally: hybrid BM25+vector query for near-miss matches
    3. Merge via RRF, deduplicate, exclude query fact's own document if requested.
    """
    candidates: dict[str, Fact] = {}

    # Step 1: Exact canonical key match
    if query_fact.canonical_key:
        exact_matches = list_facts_for_canonical_key(query_fact.canonical_key, db_path)
        for fact, _ in exact_matches:
            if fact.id != query_fact.id:
                candidates[fact.id] = fact

    # Step 2: Hybrid retrieval for near-miss matches
    query_sentence = _fact_to_sentence(query_fact)

    bm25 = BM25Index()
    bm25.build(db_path)
    bm25_results = bm25.query(query_sentence, top_k=top_k)

    vec = VectorIndex()
    vec.build(db_path)
    vec_results = vec.query(query_sentence, top_k=top_k)

    hybrid = reciprocal_rank_fusion(bm25_results, vec_results)
    for fact, _ in hybrid:
        if fact.id != query_fact.id:
            candidates[fact.id] = fact

    # Filter out same-document facts if requested
    result = list(candidates.values())
    if exclude_document_id:
        result = [f for f in result if f.document_id != exclude_document_id]

    return result[:top_k]
