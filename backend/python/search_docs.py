import sys
import json
from vector_store import search_documents

if __name__ == "__main__":
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    results = search_documents(query, limit)
    print(json.dumps(results))
