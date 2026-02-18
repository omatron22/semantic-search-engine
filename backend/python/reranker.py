"""
Cross-encoder reranker using sentence-transformers CrossEncoder.
Lazy-loads model on first use for fast startup.
"""

_model = None
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_model():
    """Lazy-load the cross-encoder model (once per process)."""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(_MODEL_NAME)
    return _model


def rerank(query, results, top_n=10):
    """
    Rerank results using cross-encoder scoring.

    Args:
        query: The search query string
        results: List of result dicts (must have 'text' field)
        top_n: Number of top results to return

    Returns:
        Top N results sorted by rerank_score descending, with rerank_score added.
        Falls back to original results if reranker fails.
    """
    if not results:
        return []

    try:
        model = _get_model()

        # Build query-passage pairs for batch scoring
        pairs = [[query, r.get("text", "")] for r in results]

        # Score all pairs in one batch
        scores = model.predict(pairs)

        # Attach scores to results
        scored = []
        for i, result in enumerate(results):
            r = dict(result)
            r["rerank_score"] = float(scores[i])
            scored.append(r)

        # Sort by rerank score descending
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)

        return scored[:top_n]

    except Exception as e:
        import sys
        print(f"Reranker failed, falling back to original order: {e}", file=sys.stderr)
        return results[:top_n]
