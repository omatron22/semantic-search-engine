const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3001;
const PYTHON_API = 'http://127.0.0.1:3002';

app.use(cors());
app.use(express.json());

const METADATA_FILE = path.join(__dirname, '..', 'storage', 'index_metadata.json');
const ENGINE_CONFIG_FILE = path.join(__dirname, '..', 'storage', 'engine_config.json');

// File types read directly by Node as plain text
const TEXT_EXTENSIONS = new Set([
  '.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx',
  '.java', '.c', '.cpp', '.h', '.go', '.rs', '.rb',
  '.php', '.swift', '.kt', '.sh', '.bash', '.zsh',
  '.sql', '.r', '.m', '.css', '.scss', '.less',
  '.log', '.ini', '.toml', '.cfg', '.conf', '.env',
  '.gitignore', '.rst', '.tex', '.rtf',
]);

// File types parsed by the Python API
const PARSED_EXTENSIONS = new Set([
  '.pdf', '.docx', '.csv', '.json',
  '.html', '.htm', '.xml',
  '.yaml', '.yml',
  '.xlsx', '.pptx',
]);

// ──────────────────────────────────────────────
// Python API helper
// ──────────────────────────────────────────────

async function pythonAPI(method, urlPath, body = null, timeout = 30000) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(timeout),
  };
  if (body !== null) {
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`${PYTHON_API}${urlPath}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Python API ${method} ${urlPath} failed (${res.status}): ${text}`);
  }
  return res.json();
}

async function waitForPythonAPI(maxWait = 30000) {
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    try {
      await pythonAPI('GET', '/health', null, 3000);
      return true;
    } catch {
      await new Promise(r => setTimeout(r, 500));
    }
  }
  throw new Error('Python API did not start in time');
}

// ──────────────────────────────────────────────
// Routes (unchanged API surface)
// ──────────────────────────────────────────────

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', message: 'Backend server running' });
});

// Engine status — check if reindex is needed
app.get('/api/engine/status', (req, res) => {
  try {
    let needsReindex = true;
    if (fs.existsSync(ENGINE_CONFIG_FILE)) {
      const config = JSON.parse(fs.readFileSync(ENGINE_CONFIG_FILE, 'utf-8'));
      const engineVersion = config.engine_version || 2;
      const lastIndexedVersion = config.last_indexed_version || 0;
      needsReindex = lastIndexedVersion < engineVersion;
    }
    res.json({ needsReindex });
  } catch (error) {
    res.json({ needsReindex: true });
  }
});

// Mark engine upgrade complete
app.post('/api/engine/upgrade-complete', (req, res) => {
  try {
    let config = {};
    if (fs.existsSync(ENGINE_CONFIG_FILE)) {
      config = JSON.parse(fs.readFileSync(ENGINE_CONFIG_FILE, 'utf-8'));
    }
    config.last_indexed_version = config.engine_version || 2;
    fs.mkdirSync(path.dirname(ENGINE_CONFIG_FILE), { recursive: true });
    fs.writeFileSync(ENGINE_CONFIG_FILE, JSON.stringify(config, null, 2));
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Ollama status check
app.get('/api/ollama/status', async (req, res) => {
  try {
    const response = await fetch('http://localhost:11434/api/tags', { signal: AbortSignal.timeout(5000) });
    const data = await response.json();
    const models = (data.models || []).map(m => m.name);
    res.json({ running: true, models });
  } catch (error) {
    res.json({ running: false, models: [] });
  }
});

// Get all indexed folders
app.get('/api/indexes', (req, res) => {
  try {
    if (fs.existsSync(METADATA_FILE)) {
      const metadata = JSON.parse(fs.readFileSync(METADATA_FILE, 'utf-8'));
      res.json(metadata);
    } else {
      res.json({ indexes: [] });
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Delete an index
app.delete('/api/indexes/:id', async (req, res) => {
  const { id } = req.params;

  try {
    await pythonAPI('DELETE', `/metadata/${id}`);
    res.json({ success: true, message: 'Index deleted' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Crawl directory endpoint
app.post('/api/crawl', (req, res) => {
  const { folderPath } = req.body;

  if (!folderPath || !fs.existsSync(folderPath)) {
    return res.status(400).json({ error: 'Invalid folder path' });
  }

  const files = crawlDirectory(folderPath);
  res.json({
    success: true,
    fileCount: files.length,
    files: files.slice(0, 10)
  });
});

// Index a folder with SSE progress streaming + metadata tracking
app.post('/api/index', async (req, res) => {
  const { folderPath, isReindex = false } = req.body;

  if (!folderPath || !fs.existsSync(folderPath)) {
    return res.status(400).json({ error: 'Invalid folder path' });
  }

  // Set up SSE
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  try {
    const allFiles = crawlDirectory(folderPath);

    // Determine which files need indexing
    let filesToIndex = allFiles;
    let skippedCount = 0;

    if (isReindex) {
      const metadataCheck = await pythonAPI('POST', '/metadata/check', {
        folder_path: folderPath,
        all_files: allFiles,
      });
      filesToIndex = metadataCheck.needsIndex;
      skippedCount = metadataCheck.unchanged.length;

      res.write(`data: ${JSON.stringify({
        type: 'info',
        message: `Found ${filesToIndex.length} new/modified files, ${skippedCount} unchanged`
      })}\n\n`);
    }

    const totalFiles = filesToIndex.length;
    let indexed = 0;
    const startTime = Date.now();
    const filesMetadata = {};

    // Send initial progress
    res.write(`data: ${JSON.stringify({
      type: 'progress',
      current: 0,
      total: totalFiles,
      currentFile: '',
      message: 'Starting indexing...'
    })}\n\n`);

    for (let i = 0; i < filesToIndex.length; i++) {
      const file = filesToIndex[i];
      const ext = file.extension.toLowerCase();

      // Send progress update
      const elapsed = Date.now() - startTime;
      const avgTimePerFile = i > 0 ? elapsed / i : 0;
      const remaining = (totalFiles - i) * avgTimePerFile;
      const eta = remaining > 0 ? Math.ceil(remaining / 1000) : 0;

      res.write(`data: ${JSON.stringify({
        type: 'progress',
        current: i + 1,
        total: totalFiles,
        currentFile: file.name,
        message: `Processing ${file.name}...`,
        eta: eta
      })}\n\n`);

      let content = null;

      try {
        if (TEXT_EXTENSIONS.has(ext)) {
          content = fs.readFileSync(file.path, 'utf-8');
        } else if (PARSED_EXTENSIONS.has(ext)) {
          const parsed = await pythonAPI('POST', '/parse', { file_path: file.path });
          content = parsed.success ? parsed.text : null;
        }

        // Index if content was extracted successfully
        if (content) {
          const indexResult = await pythonAPI('POST', '/index', {
            file_path: file.path,
            content: content,
          });

          if (indexResult.success) {
            filesMetadata[file.path] = {
              hash: indexResult.file_hash,
              chunks: indexResult.chunk_count,
              indexed_at: new Date().toISOString(),
              size: file.size
            };
            indexed++;
          }
        }
      } catch (error) {
        // Skip files that fail to index
        console.error(`Failed to index ${file.path}:`, error.message);
      }
    }

    // Update metadata
    await pythonAPI('POST', '/metadata/update', {
      folder_path: folderPath,
      files_metadata: filesMetadata,
    });

    // Mark engine upgrade complete after successful indexing
    try {
      let config = {};
      if (fs.existsSync(ENGINE_CONFIG_FILE)) {
        config = JSON.parse(fs.readFileSync(ENGINE_CONFIG_FILE, 'utf-8'));
      }
      config.last_indexed_version = config.engine_version || 2;
      fs.mkdirSync(path.dirname(ENGINE_CONFIG_FILE), { recursive: true });
      fs.writeFileSync(ENGINE_CONFIG_FILE, JSON.stringify(config, null, 2));
    } catch (e) {
      // Non-critical
    }

    // Send completion
    res.write(`data: ${JSON.stringify({
      type: 'complete',
      success: true,
      totalFiles: totalFiles,
      indexed: indexed,
      skipped: skippedCount,
      message: `Successfully indexed ${indexed} documents${skippedCount > 0 ? `, skipped ${skippedCount} unchanged` : ''}`
    })}\n\n`);

    res.end();
  } catch (error) {
    res.write(`data: ${JSON.stringify({
      type: 'error',
      error: error.message
    })}\n\n`);
    res.end();
  }
});

// Search documents (WITH METADATA + new pipeline output format)
app.post('/api/search', async (req, res) => {
  const { query, limit = 10, reranker, expansion, hybrid } = req.body;

  if (!query) {
    return res.status(400).json({ error: 'No query provided' });
  }

  // Build options for search pipeline
  const options = {};
  if (reranker !== undefined) options.reranker = reranker;
  if (expansion !== undefined) options.expansion = expansion;
  if (hybrid !== undefined) options.hybrid = hybrid;

  try {
    const searchOutput = await pythonAPI('POST', '/search', {
      query,
      limit,
      options,
    }, 60000);

    const results = searchOutput.results || [];
    const meta = searchOutput.meta || {};

    // Enrich results with file metadata
    const enrichedResults = results.map(result => {
      try {
        const stats = fs.statSync(result.file_path);
        return {
          ...result,
          file_size: stats.size,
          modified_date: stats.mtime,
          word_count: result.text ? result.text.split(/\s+/).length : 0
        };
      } catch (error) {
        return result;
      }
    });

    res.json({
      success: true,
      query: query,
      results: enrichedResults,
      meta: meta
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ──────────────────────────────────────────────
// Connectors — proxy to Python API
// ──────────────────────────────────────────────

// Add connector
app.post('/api/connectors', async (req, res) => {
  try {
    const result = await pythonAPI('POST', '/connectors', req.body);
    res.json(result);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// List connectors
app.get('/api/connectors', async (req, res) => {
  try {
    const result = await pythonAPI('GET', '/connectors');
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// List connector types
app.get('/api/connectors/types', async (req, res) => {
  try {
    const result = await pythonAPI('GET', '/connectors/types');
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Delete connector
app.delete('/api/connectors/:id', async (req, res) => {
  try {
    const result = await pythonAPI('DELETE', `/connectors/${req.params.id}`);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Manual sync (SSE streaming)
app.post('/api/connectors/:id/sync', async (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  try {
    const response = await fetch(`${PYTHON_API}/connectors/${req.params.id}/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(300000), // 5 min timeout for sync
    });

    if (!response.ok) {
      const text = await response.text();
      res.write(`data: ${JSON.stringify({ type: 'error', error: text })}\n\n`);
      res.end();
      return;
    }

    // Stream SSE from Python to client
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      res.write(decoder.decode(value, { stream: true }));
    }

    res.end();
  } catch (error) {
    res.write(`data: ${JSON.stringify({ type: 'error', error: error.message })}\n\n`);
    res.end();
  }
});

// Connector status
app.get('/api/connectors/:id/status', async (req, res) => {
  try {
    const result = await pythonAPI('GET', `/connectors/${req.params.id}/status`);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ──────────────────────────────────────────────
// Helper: Crawl directory (unchanged, pure Node)
// ──────────────────────────────────────────────

function crawlDirectory(dirPath, fileList = []) {
  const files = fs.readdirSync(dirPath);

  files.forEach(file => {
    const filePath = path.join(dirPath, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      crawlDirectory(filePath, fileList);
    } else {
      fileList.push({
        path: filePath,
        name: file,
        extension: path.extname(file),
        size: stat.size,
        modified: stat.mtime
      });
    }
  });

  return fileList;
}

// ──────────────────────────────────────────────
// Static file serving (production)
// ──────────────────────────────────────────────

const DIST_DIR = path.join(__dirname, '..', '..', 'dist');
if (fs.existsSync(DIST_DIR)) {
  app.use(express.static(DIST_DIR));
  app.get('*', (req, res) => {
    res.sendFile(path.join(DIST_DIR, 'index.html'));
  });
}

// ──────────────────────────────────────────────
// Startup: wait for Python API, then listen
// ──────────────────────────────────────────────

(async () => {
  try {
    console.log('Waiting for Python API (FastAPI :3002)...');
    await waitForPythonAPI();
    console.log('Python API is ready.');
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }

  app.listen(PORT, () => {
    console.log(`Backend server running on http://localhost:${PORT}`);
    console.log(`Crawl API: POST /api/crawl`);
    console.log(`Index API: POST /api/index (with SSE progress + metadata)`);
    console.log(`  Supported: TXT, MD, PDF, DOCX, CSV, JSON, HTML, XML, YAML, XLSX, PPTX + code files`);
    console.log(`Search API: POST /api/search`);
    console.log(`Indexes API: GET /api/indexes`);
    console.log(`Engine Status: GET /api/engine/status`);
    console.log(`Ollama Status: GET /api/ollama/status`);
    console.log(`Connectors: GET/POST /api/connectors, DELETE /api/connectors/:id`);
    console.log(`Connector Sync: POST /api/connectors/:id/sync`);
  });
})();
