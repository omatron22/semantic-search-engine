import lancedb
from sentence_transformers import SentenceTransformer
import os

# Initialize
DB_PATH = "../storage/vector_db"
model = SentenceTransformer('all-MiniLM-L6-v2')

def init_db():
    """Initialize LanceDB"""
    os.makedirs(DB_PATH, exist_ok=True)
    db = lancedb.connect(DB_PATH)
    return db

def store_document(file_path, text, metadata=None):
    """Store a document's embedding"""
    db = init_db()
    
    # Generate embedding
    embedding = model.encode(text).tolist()
    
    # Prepare data
    data = [{
        "vector": embedding,
        "text": text[:500],  # Store first 500 chars
        "file_path": file_path,
        "metadata": str(metadata or {})
    }]
    
    # Create or append to table
    try:
        table = db.open_table("documents")
        table.add(data)
    except:
        table = db.create_table("documents", data)
    
    return True

def search_documents(query, limit=10):
    """Search for similar documents"""
    db = init_db()
    
    # Generate query embedding
    query_vector = model.encode(query).tolist()
    
    # Search
    try:
        table = db.open_table("documents")
        results = table.search(query_vector).limit(limit).to_list()
        return results
    except:
        return []

if __name__ == "__main__":
    # Test storage
    print("Testing LanceDB storage...")
    
    # Store test documents
    store_document(
        "test1.txt",
        "This document is about corporate mergers and acquisitions",
        {"type": "test"}
    )
    
    store_document(
        "test2.txt", 
        "This document discusses vector databases and embeddings",
        {"type": "test"}
    )
    
    print("✅ Stored 2 test documents")
    
    # Test search
    results = search_documents("database technology", limit=2)
    
    print(f"\n🔍 Search results for 'database technology':")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['file_path']}: {result['text'][:60]}...")
        print(f"   Distance: {result['_distance']:.4f}\n")
