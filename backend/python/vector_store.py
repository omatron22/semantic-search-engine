import lancedb
from sentence_transformers import SentenceTransformer
import os
from index_metadata import get_file_hash
from chunker import chunk_text
from config import get_embedding_model, get_table_name

# Initialize
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "storage", "vector_db")
model = SentenceTransformer(get_embedding_model())

def init_db():
    """Initialize LanceDB"""
    os.makedirs(DB_PATH, exist_ok=True)
    db = lancedb.connect(DB_PATH)
    return db

def store_document(file_path, text, metadata=None):
    """Store a document's chunks as separate embeddings with full text."""
    db = init_db()
    table_name = get_table_name()

    # Delete existing rows for this file (clean re-index)
    try:
        table = db.open_table(table_name)
        escaped = file_path.replace("'", "''")
        table.delete(f"file_path = '{escaped}'")
    except:
        pass

    # Chunk the text
    chunks = chunk_text(text)
    if not chunks:
        return 0

    # Batch-embed all chunks at once
    chunk_texts = [c["text"] for c in chunks]
    embeddings = model.encode(chunk_texts)

    # Get file hash for tracking
    file_hash = get_file_hash(file_path)

    # Prepare rows — one per chunk, full text stored
    data = []
    for i, chunk in enumerate(chunks):
        data.append({
            "vector": embeddings[i].tolist(),
            "text": chunk["text"],
            "file_path": file_path,
            "file_hash": file_hash,
            "chunk_index": chunk["chunk_index"],
            "total_chunks": chunk["total_chunks"],
            "metadata": str(metadata or {})
        })

    # Create or append to table
    try:
        table = db.open_table(table_name)
        table.add(data)
    except:
        table = db.create_table(table_name, data)

    return len(chunks)

def delete_document(file_path):
    """Delete a document from the index"""
    db = init_db()
    table_name = get_table_name()

    try:
        table = db.open_table(table_name)
        escaped = file_path.replace("'", "''")
        table.delete(f"file_path = '{escaped}'")
        return True
    except Exception as e:
        print(f"Error deleting document: {e}")
        return False

def search_documents(query, limit=10):
    """Search for similar documents"""
    db = init_db()
    table_name = get_table_name()

    # Generate query embedding
    query_vector = model.encode(query).tolist()

    # Search
    try:
        table = db.open_table(table_name)
        results = table.search(query_vector).limit(limit).to_list()
        return results
    except:
        return []

def get_indexed_count():
    """Get total number of indexed chunks"""
    db = init_db()
    table_name = get_table_name()
    try:
        table = db.open_table(table_name)
        return table.count_rows()
    except:
        return 0
