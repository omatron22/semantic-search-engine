const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', message: 'Backend server running' });
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

// NEW: Index a folder
app.post('/api/index', async (req, res) => {
  const { folderPath } = req.body;
  
  if (!folderPath || !fs.existsSync(folderPath)) {
    return res.status(400).json({ error: 'Invalid folder path' });
  }
  
  try {
    const files = crawlDirectory(folderPath);
    let indexed = 0;
    
    for (const file of files) {
      // Only index text files for now
      if (['.txt', '.md'].includes(file.extension.toLowerCase())) {
        const content = fs.readFileSync(file.path, 'utf-8');
        await indexDocument(file.path, content);
        indexed++;
      }
    }
    
    res.json({ 
      success: true, 
      totalFiles: files.length,
      indexed: indexed,
      message: `Indexed ${indexed} documents`
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// NEW: Search documents
app.post('/api/search', async (req, res) => {
  const { query, limit = 10 } = req.body;
  
  if (!query) {
    return res.status(400).json({ error: 'No query provided' });
  }
  
  try {
    const results = await searchDocuments(query, limit);
    res.json({ 
      success: true, 
      query: query,
      results: results
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Helper: Crawl directory
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

// Helper: Index a document
function indexDocument(filePath, content) {
  return new Promise((resolve, reject) => {
    const pythonPath = '../../venv/bin/python';
    const scriptPath = '../python/index_doc.py';
    
    const python = spawn(pythonPath, [scriptPath, filePath, content]);
    
    let output = '';
    
    python.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    python.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Indexing failed for ${filePath}`));
      } else {
        resolve(output);
      }
    });
  });
}

// Helper: Search documents
function searchDocuments(query, limit) {
  return new Promise((resolve, reject) => {
    const pythonPath = '../../venv/bin/python';
    const scriptPath = '../python/search_docs.py';
    
    const python = spawn(pythonPath, [scriptPath, query, limit.toString()]);
    
    let output = '';
    
    python.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    python.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Search failed`));
      } else {
        try {
          resolve(JSON.parse(output));
        } catch (e) {
          reject(new Error(`Failed to parse search results`));
        }
      }
    });
  });
}

app.listen(PORT, () => {
  console.log(`🚀 Backend server running on http://localhost:${PORT}`);
  console.log(`📁 Crawl API: POST /api/crawl`);
  console.log(`📚 Index API: POST /api/index`);
  console.log(`🔍 Search API: POST /api/search`);
});
