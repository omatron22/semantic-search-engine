"""
BM25 keyword search implementation using only stdlib.
Simple tokenizer + TF-IDF style scoring.
"""

import math
import re
from collections import Counter


def tokenize(text):
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove stopwords."""
    tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def bm25_search(query, documents, top_n=20):
    """
    BM25 keyword search over a list of documents.

    Args:
        query: search query string
        documents: list of dicts with 'text' field (and any other fields)
        top_n: number of results to return

    Returns:
        list of (index, score) tuples sorted by score descending
    """
    if not documents or not query:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # Tokenize all documents
    doc_tokens = [tokenize(doc.get("text", "")) for doc in documents]

    # Calculate document lengths and average
    doc_lengths = [len(dt) for dt in doc_tokens]
    avg_dl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1

    N = len(documents)

    # Document frequency for each query term
    df = Counter()
    for tokens in doc_tokens:
        unique = set(tokens)
        for token in query_tokens:
            if token in unique:
                df[token] += 1

    # BM25 parameters
    k1 = 1.5
    b = 0.75

    # Score each document
    scores = []
    for i, tokens in enumerate(doc_tokens):
        if not tokens:
            scores.append(0.0)
            continue

        tf = Counter(tokens)
        score = 0.0

        for term in query_tokens:
            if term not in tf:
                continue

            # IDF component
            n = df.get(term, 0)
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1)

            # TF component with length normalization
            term_freq = tf[term]
            tf_norm = (term_freq * (k1 + 1)) / (term_freq + k1 * (1 - b + b * doc_lengths[i] / avg_dl))

            score += idf * tf_norm

        scores.append(score)

    # Get top N by score
    indexed_scores = [(i, s) for i, s in enumerate(scores) if s > 0]
    indexed_scores.sort(key=lambda x: x[1], reverse=True)

    return indexed_scores[:top_n]


# Common English stopwords
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "shall", "should", "may", "might", "must", "can", "could",
    "not", "no", "nor", "so", "if", "then", "than", "too", "very",
    "just", "about", "above", "after", "again", "all", "also", "am",
    "any", "because", "before", "between", "both", "each", "few",
    "here", "how", "into", "it", "its", "me", "more", "most", "my",
    "new", "now", "only", "other", "our", "out", "own", "re", "same",
    "she", "he", "some", "such", "that", "their", "them", "there",
    "these", "they", "this", "those", "through", "under", "until", "up",
    "we", "what", "when", "where", "which", "while", "who", "whom",
    "why", "you", "your",
}
