"""
FastAPI server — persistent Python backend for Coffee.
Loads the SentenceTransformer model once at startup, serves all Python
operations over HTTP on 127.0.0.1:3002.
"""

import sys
import os

# Ensure the python package directory is on sys.path so sibling modules resolve
sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import asyncio

# --- Imports from existing modules (model loads here, once) ---
from vector_store import store_document, delete_document, search_documents
from index_metadata import (
    get_file_hash,
    get_files_needing_index,
    update_index_metadata,
    delete_index,
)
from config import is_feature_enabled
from search_docs import deduplicate_results, merge_vector_results

# Connector framework
import connectors  # registers all connector types
from connectors import connector_registry
from sync_engine import sync_connector, start_all_schedules, stop_all_schedules, add_schedule, remove_schedule

# Parser functions
from parse_pdf import extract_text_from_pdf
from parse_docx import extract_text_from_docx
from parse_csv import extract_text_from_csv
from parse_json import extract_text_from_json
from parse_html import extract_text_from_html
from parse_yaml import extract_text_from_yaml
from parse_xlsx import extract_text_from_xlsx
from parse_pptx import extract_text_from_pptx

@asynccontextmanager
async def lifespan(app):
    """Start sync engine on startup, stop on shutdown."""
    start_all_schedules()
    yield
    stop_all_schedules()

app = FastAPI(lifespan=lifespan)

# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": True}

# ──────────────────────────────────────────────
# Parse — replaces parse_pdf/docx/csv/json.py
# ──────────────────────────────────────────────

class ParseRequest(BaseModel):
    file_path: str

PARSERS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".csv": extract_text_from_csv,
    ".json": extract_text_from_json,
    ".html": extract_text_from_html,
    ".htm": extract_text_from_html,
    ".xml": extract_text_from_html,
    ".yaml": extract_text_from_yaml,
    ".yml": extract_text_from_yaml,
    ".xlsx": extract_text_from_xlsx,
    ".pptx": extract_text_from_pptx,
}

@app.post("/parse")
def parse_file(req: ParseRequest):
    ext = os.path.splitext(req.file_path)[1].lower()
    parser = PARSERS.get(ext)
    if not parser:
        return {"success": False, "text": None, "error": f"Unsupported file type: {ext}"}
    try:
        text = parser(req.file_path)
        if text and text.startswith("Error"):
            return {"success": False, "text": None, "error": text}
        return {"success": True, "text": text}
    except Exception as e:
        return {"success": False, "text": None, "error": str(e)}

# ──────────────────────────────────────────────
# Index — replaces index_doc.py
# ──────────────────────────────────────────────

class IndexRequest(BaseModel):
    file_path: str
    content: str

@app.post("/index")
def index_document(req: IndexRequest):
    try:
        chunk_count = store_document(req.file_path, req.content)
        file_hash = get_file_hash(req.file_path)
        return {"success": True, "file_hash": file_hash, "chunk_count": chunk_count}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ──────────────────────────────────────────────
# Search — replaces search_docs.py __main__
# ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    options: Optional[dict] = None

@app.post("/search")
def search(req: SearchRequest):
    query = req.query
    limit = req.limit
    options = req.options or {}

    use_expansion = options.get("expansion", is_feature_enabled("query_expansion"))
    use_hybrid = options.get("hybrid", is_feature_enabled("hybrid_search"))
    use_reranker = options.get("reranker", is_feature_enabled("reranker"))

    meta = {
        "used_llm": False,
        "expanded_queries": [query],
        "hints": {},
    }

    # Step 1: Query Expansion
    expanded_queries = [query]
    if use_expansion:
        try:
            from query_expand import expand_query
            expansion = expand_query(query)
            expanded_queries = expansion["queries"]
            meta["used_llm"] = expansion["used_llm"]
            meta["expanded_queries"] = expanded_queries
            meta["hints"] = expansion["hints"]
        except Exception:
            pass

    # Step 2: Vector Search per expanded query
    all_vector_results = []
    candidates_per_query = max(50, limit * 5)
    for q in expanded_queries:
        results = search_documents(q, candidates_per_query)
        all_vector_results.extend(results)

    merged = merge_vector_results(all_vector_results)

    # Step 3: Hybrid BM25 + RRF
    if use_hybrid and merged:
        try:
            from hybrid_search import hybrid_merge
            merged = hybrid_merge(query, merged, top_n=limit * 3)
        except Exception:
            pass

    # Step 4: Deduplicate
    deduplicated = deduplicate_results(merged, limit * 2)

    # Step 5: Rerank
    if use_reranker and deduplicated:
        try:
            from reranker import rerank
            deduplicated = rerank(query, deduplicated, top_n=limit)
        except Exception:
            deduplicated = deduplicated[:limit]
    else:
        deduplicated = deduplicated[:limit]

    return {"results": deduplicated, "meta": meta}

# ──────────────────────────────────────────────
# Metadata — replaces index_metadata.py CLI
# ──────────────────────────────────────────────

class MetadataCheckRequest(BaseModel):
    folder_path: str
    all_files: list

@app.post("/metadata/check")
def metadata_check(req: MetadataCheckRequest):
    needs_index, unchanged, deleted = get_files_needing_index(req.folder_path, req.all_files)
    return {"needsIndex": needs_index, "unchanged": unchanged, "deleted": deleted}


class MetadataUpdateRequest(BaseModel):
    folder_path: str
    files_metadata: dict

@app.post("/metadata/update")
def metadata_update(req: MetadataUpdateRequest):
    update_index_metadata(req.folder_path, req.files_metadata)
    return {"success": True}


@app.delete("/metadata/{index_id}")
def metadata_delete(index_id: str):
    delete_index(index_id)
    return {"success": True}


# ──────────────────────────────────────────────
# Connectors — CRUD + sync
# ──────────────────────────────────────────────

class AddConnectorRequest(BaseModel):
    type: str
    credentials: dict
    label: str = ""
    sync_interval: int = 30

@app.post("/connectors")
def add_connector(req: AddConnectorRequest):
    try:
        status = connector_registry.add_connector(
            connector_type=req.type,
            credentials=req.credentials,
            label=req.label,
            sync_interval=req.sync_interval,
        )
        # Schedule background sync
        add_schedule(status["connector_id"], req.sync_interval)
        return {"success": True, "connector": status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/connectors")
def list_connectors():
    return {"connectors": connector_registry.list_connectors()}

@app.get("/connectors/types")
def list_connector_types():
    return {"types": connector_registry.get_available_types()}

@app.delete("/connectors/{connector_id}")
def remove_connector(connector_id: str):
    from index_metadata import load_metadata, save_metadata

    # Get connector and items folder BEFORE removing
    connector = connector_registry.get_connector(connector_id)
    items_folder = connector.get_items_folder() if connector else None

    # Clean up vector store entries BEFORE files are deleted
    if items_folder and os.path.exists(items_folder):
        for f in os.listdir(items_folder):
            if f.endswith(".txt"):
                delete_document(os.path.join(items_folder, f))

    # Remove connector (deletes files + config entry)
    connector_registry.remove_connector(connector_id)
    remove_schedule(connector_id)

    # Delete the index metadata entry
    if items_folder:
        metadata = load_metadata()
        metadata["indexes"] = [
            idx for idx in metadata["indexes"] if idx["path"] != items_folder
        ]
        save_metadata(metadata)

    return {"success": True}

@app.post("/connectors/{connector_id}/sync")
async def trigger_sync(connector_id: str):
    """Trigger a manual sync with SSE progress streaming."""
    connector = connector_registry.get_connector(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    async def event_stream():
        messages = []

        def progress_cb(msg):
            messages.append(msg)

        result = await sync_connector(connector_id, progress_callback=progress_cb)

        # Send progress messages
        for msg in messages:
            yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"

        # Send final result
        yield f"data: {json.dumps({'type': 'complete', **result})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/connectors/{connector_id}/status")
def connector_status(connector_id: str):
    connector = connector_registry.get_connector(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector.get_status()


# ──────────────────────────────────────────────
# Run with uvicorn
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3002, log_level="info")
