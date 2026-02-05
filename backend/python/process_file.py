import sys
import json
from sentence_transformers import SentenceTransformer

# Load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

def process_text(text):
    """Generate embedding for text"""
    embedding = model.encode(text)
    return embedding.tolist()  # Convert to list for JSON

if __name__ == "__main__":
    # Read input from Node.js via command line
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No text provided"}))
        sys.exit(1)
    
    text = sys.argv[1]
    
    # Generate embedding
    embedding = process_text(text)
    
    # Return JSON result to Node.js
    result = {
        "text": text[:50] + "..." if len(text) > 50 else text,
        "embedding_length": len(embedding),
        "embedding": embedding[:5]  # First 5 values for testing
    }
    
    print(json.dumps(result))
