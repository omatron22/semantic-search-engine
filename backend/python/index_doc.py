import sys
from vector_store import store_document

if __name__ == "__main__":
    file_path = sys.argv[1]
    content = sys.argv[2]
    
    store_document(file_path, content)
    print(f"Indexed: {file_path}")
