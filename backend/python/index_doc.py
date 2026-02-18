import sys
from vector_store import store_document
from index_metadata import get_file_hash

if __name__ == "__main__":
    file_path = sys.argv[1]

    # Read content from stdin instead of argv (handles newlines properly)
    content = sys.stdin.read()

    # Store document with hash — returns chunk count
    chunk_count = store_document(file_path, content)

    # Return file metadata for tracking (includes chunk count)
    file_hash = get_file_hash(file_path)
    print(f"Indexed: {file_path} | Hash: {file_hash} | Chunks: {chunk_count}")
