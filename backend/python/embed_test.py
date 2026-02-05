from sentence_transformers import SentenceTransformer

# Load small embedding model (will download ~80MB first time)
print("Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# Test embedding a simple query
query = "Find documents about mergers"
embedding = model.encode(query)

print(f"Query: {query}")
print(f"Embedding dimensions: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")
print("✅ Embedding model works!")
