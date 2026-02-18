import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import './IndexPage.css';

const API_BASE = "http://localhost:3001";

interface ProgressData {
  current: number;
  total: number;
  currentFile: string;
  eta: number;
}

interface IndexedFolder {
  id: string;
  path: string;
  indexed_at: string;
  file_count: number;
  files: Record<string, any>;
}

export function IndexPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [selectedFolder, setSelectedFolder] = useState("");
  const [indexing, setIndexing] = useState(false);
  const [progress, setProgress] = useState<ProgressData>({ current: 0, total: 0, currentFile: "", eta: 0 });
  const [indexedFolders, setIndexedFolders] = useState<IndexedFolder[]>([]);
  const [loadingIndexes, setLoadingIndexes] = useState(true);
  const [needsReindex, setNeedsReindex] = useState(false);

  useEffect(() => {
    loadIndexedFolders();
    checkEngineStatus();
  }, []);

  const loadIndexedFolders = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/indexes`);
      const data = await response.json();
      setIndexedFolders(data.indexes || []);
    } catch (error) {
      console.error("Failed to load indexes");
    } finally {
      setLoadingIndexes(false);
    }
  };

  const checkEngineStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/engine/status`);
      const data = await response.json();
      setNeedsReindex(data.needsReindex);
    } catch (error) {
      // Server not running yet
    }
  };

  const indexFolder = async (folderPath?: string, isReindex = false) => {
    const pathToIndex = folderPath || selectedFolder;
    
    if (!pathToIndex) {
      setStatus("Please select a folder first");
      return;
    }

    setIndexing(true);
    setStatus(isReindex ? "Re-indexing..." : "Preparing to index...");
    setProgress({ current: 0, total: 0, currentFile: "", eta: 0 });
    
    try {
      const response = await fetch(`${API_BASE}/api/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folderPath: pathToIndex, isReindex })
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response stream");
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'progress') {
              setProgress({
                current: data.current,
                total: data.total,
                currentFile: data.currentFile,
                eta: data.eta || 0
              });
              setStatus(data.message);
            } else if (data.type === 'complete') {
              setStatus(data.message);
              setIndexing(false);
              setNeedsReindex(false);
              await loadIndexedFolders();
              if (!isReindex) {
                setTimeout(() => navigate('/search'), 2000);
              }
            } else if (data.type === 'error') {
              setStatus(`Error: ${data.error}`);
              setIndexing(false);
            } else if (data.type === 'info') {
              setStatus(data.message);
            }
          }
        }
      }
    } catch (error) {
      setStatus("Indexing failed");
      setIndexing(false);
    }
  };

  const deleteIndex = async (indexId: string) => {
    if (!confirm("Are you sure you want to delete this index?")) {
      return;
    }

    try {
      await fetch(`${API_BASE}/api/indexes/${indexId}`, {
        method: "DELETE"
      });
      setStatus("Index deleted");
      await loadIndexedFolders();
    } catch (error) {
      setStatus("Failed to delete index");
    }
  };

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const percentage = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  return (
    <div className="page">
      <div className="page-container">
        <div className="page-hero">
          <h1>Search anything, find everything</h1>
          <p className="hero-description">
            Index your folders once, search instantly forever. Add new documents and re-index only what changed.
          </p>
        </div>

        {needsReindex && indexedFolders.length > 0 && (
          <div className="reindex-banner">
            Search engine upgraded. Please re-index your folders for improved search quality.
          </div>
        )}

        {/* Add New Folder Section */}
        <div className="add-folder-section">
          <h2>Add folder to index</h2>
          
          <div className="folder-input-group">
            <input
              type="text"
              className="folder-input"
              value={selectedFolder}
              onChange={(e) => setSelectedFolder(e.target.value)}
              placeholder="/path/to/documents"
              disabled={indexing}
            />
            <button
              onClick={() => indexFolder()}
              disabled={!selectedFolder.trim() || indexing}
              className="btn btn-primary"
            >
              {indexing ? "Indexing..." : "Start indexing"}
            </button>
          </div>

          {indexing && progress.total > 0 && (
            <div className="progress-container">
              <div className="progress-info">
                <span className="progress-stats">
                  {progress.current} / {progress.total} files ({percentage}%)
                </span>
                {progress.eta > 0 && (
                  <span className="progress-eta">
                    {formatTime(progress.eta)} remaining
                  </span>
                )}
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${percentage}%` }} />
              </div>
              {progress.currentFile && (
                <div className="progress-file">
                  {progress.currentFile}
                </div>
              )}
            </div>
          )}

          {status && (
            <div className={`status-message ${indexing ? 'loading' : ''}`}>
              {status}
            </div>
          )}
        </div>

        {/* Indexed Folders Section */}
        {indexedFolders.length > 0 && (
          <div className="indexed-section">
            <h2>Indexed folders</h2>
            <div className="indexed-list">
              {indexedFolders.map((folder) => (
                <div key={folder.id} className="indexed-item">
                  <div className="indexed-info">
                    <div className="indexed-path">{folder.path}</div>
                    <div className="indexed-meta">
                      {folder.file_count} files • Indexed {formatDate(folder.indexed_at)}
                    </div>
                  </div>
                  <div className="indexed-actions">
                    <button
                      onClick={() => navigate('/search')}
                      className="btn-action"
                    >
                      Search
                    </button>
                    <button
                      onClick={() => indexFolder(folder.path, true)}
                      className="btn-action"
                      disabled={indexing}
                    >
                      Re-index
                    </button>
                    <button
                      onClick={() => deleteIndex(folder.id)}
                      className="btn-action btn-danger"
                      disabled={indexing}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="info-section">
          <div className="info-label">Supported formats</div>
          <div className="file-types">
            <span className="file-badge">PDF</span>
            <span className="file-badge">TXT</span>
            <span className="file-badge">MD</span>
            <span className="file-badge">DOCX</span>
            <span className="file-badge">CSV</span>
            <span className="file-badge">JSON</span>
          </div>
        </div>
      </div>
    </div>
  );
}
