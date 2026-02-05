import { useState } from "react";
import "./App.css";

function App() {
  const [status, setStatus] = useState<string>("Not connected");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [results, setResults] = useState<any[]>([]);

  // Test backend connection
  const testConnection = async () => {
    try {
      const response = await fetch("http://localhost:3001/health");
      const data = await response.json();
      setStatus(`✅ Connected: ${data.message}`);
    } catch (error) {
      setStatus("❌ Backend not running");
    }
  };

  // Index the public folder
  const indexFolder = async () => {
    setStatus("📚 Indexing...");
    try {
      const response = await fetch("http://localhost:3001/api/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          folderPath: "/Users/omaresp/Desktop/semantic-search-engine/tauri-app/public"
        })
      });
      const data = await response.json();
      setStatus(`✅ ${data.message}`);
    } catch (error) {
      setStatus("❌ Indexing failed");
    }
  };

  // Search documents
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!searchQuery.trim()) return;
    
    setStatus("🔍 Searching...");
    try {
      const response = await fetch("http://localhost:3001/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          limit: 10
        })
      });
      const data = await response.json();
      setResults(data.results);
      setStatus(`✅ Found ${data.results.length} results`);
    } catch (error) {
      setStatus("❌ Search failed");
    }
  };

  return (
    <main className="container">
      <h1>Semantic Search Engine</h1>
      
      <div style={{ margin: "20px" }}>
        <h2>Status</h2>
        <p>{status}</p>
        
        <div style={{ marginBottom: "20px" }}>
          <button onClick={testConnection} style={{ margin: "5px" }}>
            Test Connection
          </button>
          
          <button onClick={indexFolder} style={{ margin: "5px" }}>
            Index Public Folder
          </button>
        </div>

        <h2>Search</h2>
        <form onSubmit={handleSearch}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search for documents..."
            style={{ 
              width: "300px", 
              padding: "8px", 
              marginRight: "10px" 
            }}
          />
          <button type="submit">Search</button>
        </form>

        {results.length > 0 && (
          <div style={{ marginTop: "20px" }}>
            <h3>Results:</h3>
            {results.map((result, i) => (
              <div 
                key={i} 
                style={{ 
                  border: "1px solid #333", 
                  padding: "10px", 
                  margin: "10px 0",
                  borderRadius: "5px"
                }}
              >
                <div><strong>{result.file_path}</strong></div>
                <div style={{ fontSize: "0.9em", color: "#aaa" }}>
                  Distance: {result._distance?.toFixed(4)}
                </div>
                <div style={{ marginTop: "5px" }}>{result.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

export default App;
