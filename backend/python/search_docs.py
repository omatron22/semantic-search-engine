import sys
import json
from vector_store import search_documents
from config import is_feature_enabled

def deduplicate_results(results, limit):
    """Keep only the best match per file (best chunk)."""
    seen = {}
    for result in results:
        file_path = result.get('file_path', '')
        distance = result.get('_distance', float('inf'))
        if file_path not in seen or distance < seen[file_path].get('_distance', float('inf')):
            seen[file_path] = result

    deduplicated = sorted(seen.values(), key=lambda x: x.get('_distance', float('inf')))
    return deduplicated[:limit]

def merge_vector_results(all_results):
    """Merge results from multiple vector searches, keeping best per file+chunk."""
    best = {}
    for result in all_results:
        key = f"{result.get('file_path', '')}::{result.get('chunk_index', 0)}"
        distance = result.get('_distance', float('inf'))
        if key not in best or distance < best[key].get('_distance', float('inf')):
            best[key] = result
    return sorted(best.values(), key=lambda x: x.get('_distance', float('inf')))

if __name__ == "__main__":
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    options = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}

    # Feature flags — can be overridden per-request via options
    use_expansion = options.get("expansion", is_feature_enabled("query_expansion"))
    use_hybrid = options.get("hybrid", is_feature_enabled("hybrid_search"))
    use_reranker = options.get("reranker", is_feature_enabled("reranker"))

    meta = {
        "used_llm": False,
        "expanded_queries": [query],
        "hints": {},
    }

    # --- Step 1: Query Expansion (optional, requires Ollama) ---
    expanded_queries = [query]
    if use_expansion:
        try:
            from query_expand import expand_query
            expansion = expand_query(query)
            expanded_queries = expansion["queries"]
            meta["used_llm"] = expansion["used_llm"]
            meta["expanded_queries"] = expanded_queries
            meta["hints"] = expansion["hints"]
        except Exception:
            pass

    # --- Step 2: Vector Search per expanded query ---
    all_vector_results = []
    candidates_per_query = max(50, limit * 5)
    for q in expanded_queries:
        results = search_documents(q, candidates_per_query)
        all_vector_results.extend(results)

    # Merge best per file+chunk across all queries
    merged = merge_vector_results(all_vector_results)

    # --- Step 3: Hybrid BM25 + RRF (optional) ---
    if use_hybrid and merged:
        try:
            from hybrid_search import hybrid_merge
            merged = hybrid_merge(query, merged, top_n=limit * 3)
        except Exception:
            pass

    # --- Step 4: Deduplicate (best chunk per file) ---
    deduplicated = deduplicate_results(merged, limit * 2)

    # --- Step 5: Cross-Encoder Rerank (optional) ---
    if use_reranker and deduplicated:
        try:
            from reranker import rerank
            deduplicated = rerank(query, deduplicated, top_n=limit)
        except Exception:
            deduplicated = deduplicated[:limit]
    else:
        deduplicated = deduplicated[:limit]

    # Output structured response
    output = {
        "results": deduplicated,
        "meta": meta,
    }
    print(json.dumps(output))
