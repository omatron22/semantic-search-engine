import { useState, useEffect } from "react";
import './SearchPage.css';

const API_BASE = "http://localhost:3001";

interface SearchResult {
  file_path: string;
  text: string;
  _distance: number;
  chunk_index?: number;
  total_chunks?: number;
  rerank_score?: number;
  rrf_score?: number;
  file_size?: number;
  modified_date?: string;
  word_count?: number;
}

interface SearchMeta {
  used_llm: boolean;
  expanded_queries: string[];
  hints: {
    people?: string[];
    topics?: string[];
    file_types?: string[];
    projects?: string[];
  };
}

export function SearchPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchMeta, setSearchMeta] = useState<SearchMeta | null>(null);
  const [ollamaStatus, setOllamaStatus] = useState<{ running: boolean; models: string[] } | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/ollama/status`)
      .then(res => res.json())
      .then(data => setOllamaStatus(data))
      .catch(() => setOllamaStatus({ running: false, models: [] }));
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!searchQuery.trim()) return;

    setSearching(true);
    setHasSearched(true);
    setSearchMeta(null);

    try {
      const response = await fetch(`${API_BASE}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery, limit: 10 })
      });
      const data = await response.json();
      setResults(data.results || []);
      if (data.meta) {
        setSearchMeta(data.meta);
      }
    } catch (error) {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const getFileInfo = (filePath: string) => {
    const parts = filePath.split('/');
    const filename = parts[parts.length - 1];
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    return { filename, extension };
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getScore = (result: SearchResult): string => {
    if (result.rerank_score !== undefined) {
      const sigmoid = 1 / (1 + Math.exp(-result.rerank_score));
      return (sigmoid * 100).toFixed(0);
    }
    return ((2 - result._distance) / 2 * 100).toFixed(0);
  };

  return (
    <div className="page">
      <div className="page-container">
        <div className="search-section">
          <h1>What are you looking for?</h1>

          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search using natural language..."
              className="search-input"
              disabled={searching}
              autoFocus
            />
            <button type="submit" className="btn-search" disabled={searching || !searchQuery.trim()}>
              {searching ? "Searching..." : "Search"}
            </button>
          </form>

          {ollamaStatus && (
            <div className={`ollama-status ${ollamaStatus.running ? 'connected' : 'disconnected'}`}>
              <span className="status-dot" />
              {ollamaStatus.running ? 'Ollama connected' : 'Ollama disconnected'}
            </div>
          )}
        </div>

        {hasSearched && (
          <div className="results-container">
            {searching ? (
              <div className="loading-state">
                <div className="spinner" />
                <p>Searching documents...</p>
              </div>
            ) : results.length > 0 ? (
              <>
                <div className="results-count">
                  {results.length} {results.length === 1 ? 'result' : 'results'}
                </div>

                {searchMeta?.used_llm && searchMeta.expanded_queries.length > 1 && (
                  <div className="expanded-queries">
                    <span className="expanded-label">Also searched for:</span>
                    <div className="expanded-tags">
                      {searchMeta.expanded_queries
                        .filter(q => q !== searchQuery)
                        .map((q, i) => (
                          <span key={i} className="expanded-tag">{q}</span>
                        ))}
                    </div>
                  </div>
                )}

                <div className="results-list">
                  {results.map((result, i) => {
                    const { filename, extension } = getFileInfo(result.file_path);
                    const score = getScore(result);

                    return (
                      <div key={i} className="result-card">
                        <div className="result-header">
                          <div className="result-title">
                            <span className={`file-badge badge-${extension}`}>
                              {extension.toUpperCase()}
                            </span>
                            <h3>{filename}</h3>
                          </div>
                          <div className="result-meta-top">
                            <span className="match-score">{score}% match</span>
                          </div>
                        </div>

                        <div className="result-content">
                          {result.text}
                        </div>

                        <div className="result-footer">
                          <span className="result-path">{result.file_path}</span>
                          {result.total_chunks != null && result.total_chunks > 1 && (
                            <span>Chunk {(result.chunk_index ?? 0) + 1} of {result.total_chunks}</span>
                          )}
                          {result.file_size && <span>{formatFileSize(result.file_size)}</span>}
                          {result.modified_date && <span>{formatDate(result.modified_date)}</span>}
                          {result.word_count && <span>{result.word_count} words</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <h3>No results found</h3>
                <p>Try a different search query or verify your documents are indexed</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
