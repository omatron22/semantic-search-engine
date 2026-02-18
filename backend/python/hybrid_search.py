"""
Hybrid search combining vector results with BM25 keyword results
using Reciprocal Rank Fusion (RRF).
"""

import lancedb
import os
from bm25_search import bm25_search
from config import get_table_name

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "storage", "vector_db")


def hybrid_merge(query, vector_results, top_n=20, k=60):
    """
    Merge vector search results with BM25 keyword search using RRF.

    Args:
        query: original search query
        vector_results: list of result dicts from vector search
        top_n: number of results to return
        k: RRF constant (default 60)

    Returns:
        Merged results with rrf_score field added, sorted by rrf_score descending.
    """
    if not vector_results:
        return []

    # Load all chunks from LanceDB for BM25 search
    all_chunks = _load_all_chunks()
    if not all_chunks:
        # No chunks available for BM25, return vector results as-is
        for r in vector_results:
            r["rrf_score"] = 0.0
        return vector_results[:top_n]

    # Run BM25 over all chunks
    bm25_results = bm25_search(query, all_chunks, top_n=50)

    # Build RRF scores
    # Key: file_path + chunk_index -> score
    rrf_scores = {}

    # Score vector results by their rank
    for rank, result in enumerate(vector_results):
        key = _result_key(result)
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)

    # Score BM25 results by their rank
    bm25_lookup = {}
    for rank, (idx, bm25_score) in enumerate(bm25_results):
        chunk = all_chunks[idx]
        key = _result_key(chunk)
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
        bm25_lookup[key] = chunk

    # Build combined result list
    # Start with vector results (they have full data)
    seen_keys = set()
    combined = []

    for result in vector_results:
        key = _result_key(result)
        r = dict(result)
        r["rrf_score"] = rrf_scores.get(key, 0)
        combined.append(r)
        seen_keys.add(key)

    # Add BM25-only results (not in vector results)
    for key, chunk in bm25_lookup.items():
        if key not in seen_keys:
            r = dict(chunk)
            r["rrf_score"] = rrf_scores.get(key, 0)
            r["_distance"] = 2.0  # max distance for BM25-only results
            combined.append(r)
            seen_keys.add(key)

    # Sort by RRF score descending
    combined.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)

    return combined[:top_n]


def _result_key(result):
    """Create a unique key for a result based on file_path and chunk_index."""
    fp = result.get("file_path", "")
    ci = result.get("chunk_index", 0)
    return f"{fp}::{ci}"


def _load_all_chunks():
    """Load all chunks from LanceDB for BM25 search."""
    try:
        db = lancedb.connect(DB_PATH)
        table_name = get_table_name()
        table = db.open_table(table_name)
        df = table.to_pandas()

        chunks = []
        for _, row in df.iterrows():
            chunks.append({
                "text": row.get("text", ""),
                "file_path": row.get("file_path", ""),
                "chunk_index": int(row.get("chunk_index", 0)),
                "total_chunks": int(row.get("total_chunks", 1)),
                "file_hash": row.get("file_hash", ""),
            })
        return chunks

    except Exception:
        return []
