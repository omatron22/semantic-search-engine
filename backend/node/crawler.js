const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// Simple recursive file crawler
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

// NEW: Call Python to generate embedding
function generateEmbedding(text) {
  return new Promise((resolve, reject) => {
    const pythonPath = '../../venv/bin/python';
    const scriptPath = '../python/process_file.py';
    
    const python = spawn(pythonPath, [scriptPath, text]);
    
    let output = '';
    
    python.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    python.stderr.on('data', (data) => {
      console.error(`Python error: ${data}`);
    });
    
    python.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Python exited with code ${code}`));
      } else {
        try {
          resolve(JSON.parse(output));
        } catch (e) {
          reject(new Error(`Failed to parse Python output: ${output}`));
        }
      }
    });
  });
}

// NEW: Test the integration
async function testIntegration() {
  console.log('Testing Node.js → Python integration...\n');
  
  const testText = "This is a document about corporate mergers and acquisitions";
  
  try {
    const result = await generateEmbedding(testText);
    console.log('✅ Integration successful!');
    console.log(`Text: ${result.text}`);
    console.log(`Embedding dimensions: ${result.embedding_length}`);
    console.log(`First 5 values: ${result.embedding}`);
  } catch (error) {
    console.error('❌ Integration failed:', error.message);
  }
}

// Run test
testIntegration();
