import json
import os
import hashlib
from datetime import datetime
from pathlib import Path

METADATA_FILE = os.path.join(os.path.dirname(__file__), "..", "storage", "index_metadata.json")

def load_metadata():
    """Load index metadata from disk"""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {"indexes": []}

def save_metadata(metadata):
    """Save index metadata to disk"""
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def get_file_hash(filepath):
    """Get file hash for change detection"""
    try:
        stat = os.stat(filepath)
        # Use size + mtime as a simple hash
        return f"{stat.st_size}_{int(stat.st_mtime)}"
    except:
        return None

def find_or_create_index(folder_path):
    """Find existing index or create new one"""
    metadata = load_metadata()
    
    # Look for existing index
    for idx in metadata["indexes"]:
        if idx["path"] == folder_path:
            return idx["id"], idx
    
    # Create new index
    index_id = hashlib.md5(folder_path.encode()).hexdigest()[:8]
    new_index = {
        "id": index_id,
        "path": folder_path,
        "indexed_at": datetime.now().isoformat(),
        "file_count": 0,
        "files": {}
    }
    metadata["indexes"].append(new_index)
    save_metadata(metadata)
    
    return index_id, new_index

def update_index_metadata(folder_path, files_indexed):
    """Update metadata after indexing"""
    metadata = load_metadata()
    
    for idx in metadata["indexes"]:
        if idx["path"] == folder_path:
            idx["indexed_at"] = datetime.now().isoformat()
            idx["file_count"] = len(files_indexed)
            idx["files"] = files_indexed
            break
    
    save_metadata(metadata)

def get_all_indexes():
    """Get all indexed folders"""
    return load_metadata()

def delete_index(index_id):
    """Delete an index from metadata"""
    metadata = load_metadata()
    metadata["indexes"] = [idx for idx in metadata["indexes"] if idx["id"] != index_id]
    save_metadata(metadata)
    return True

def get_files_needing_index(folder_path, all_files):
    """Determine which files need to be indexed (new or modified)"""
    metadata = load_metadata()
    
    # Find existing index
    existing_index = None
    for idx in metadata["indexes"]:
        if idx["path"] == folder_path:
            existing_index = idx
            break
    
    if not existing_index:
        # No existing index, all files need indexing
        return all_files, [], []
    
    existing_files = existing_index.get("files", {})
    
    new_files = []
    modified_files = []
    unchanged_files = []
    
    for file_info in all_files:
        filepath = file_info["path"]
        current_hash = get_file_hash(filepath)
        
        if filepath not in existing_files:
            # New file
            new_files.append(file_info)
        elif existing_files[filepath].get("hash") != current_hash:
            # Modified file
            modified_files.append(file_info)
        else:
            # Unchanged file
            unchanged_files.append(file_info)
    
    # Find deleted files
    current_paths = {f["path"] for f in all_files}
    deleted_files = [fp for fp in existing_files.keys() if fp not in current_paths]
    
    return new_files + modified_files, unchanged_files, deleted_files

if __name__ == "__main__":
    # Test
    print("Testing metadata manager...")
    
    # Create test index
    index_id, index = find_or_create_index("/test/folder")
    print(f"✅ Created index: {index_id}")
    
    # Update with files
    test_files = {
        "/test/folder/file1.txt": {
            "hash": "123_456",
            "indexed_at": datetime.now().isoformat()
        }
    }
    update_index_metadata("/test/folder", test_files)
    print("✅ Updated metadata")
    
    # Get all indexes
    all_indexes = get_all_indexes()
    print(f"✅ Found {len(all_indexes['indexes'])} indexes")

# CLI interface for Node.js integration
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: index_metadata.py [command] [args...]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check":
        # Check which files need indexing
        folder_path = sys.argv[2]
        all_files = json.loads(sys.argv[3])
        
        needs_index, unchanged, deleted = get_files_needing_index(folder_path, all_files)
        
        result = {
            "needsIndex": needs_index,
            "unchanged": unchanged,
            "deleted": deleted
        }
        print(json.dumps(result))
    
    elif command == "update":
        # Update index metadata
        folder_path = sys.argv[2]
        files_metadata = json.loads(sys.argv[3])
        
        update_index_metadata(folder_path, files_metadata)
        print("Updated")
    
    elif command == "delete":
        # Delete an index
        index_id = sys.argv[2]
        delete_index(index_id)
        print("Deleted")
    
    elif command == "list":
        # List all indexes
        indexes = get_all_indexes()
        print(json.dumps(indexes))
