"""
Background sync engine — schedules connector syncs and indexes new content.

Runs as asyncio tasks in FastAPI's event loop. Blocking IMAP I/O runs in a
thread pool via run_in_executor. After sync, new .txt files are indexed
through the existing pipeline (store_document + index_metadata).
"""

import asyncio
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from connectors import connector_registry
from connectors.base_connector import ConnectorStatus
from vector_store import store_document, delete_document
from index_metadata import find_or_create_index, update_index_metadata, get_file_hash

# Thread pool for blocking IMAP I/O
_executor = ThreadPoolExecutor(max_workers=2)

# Guard against concurrent syncs on the same connector
_syncing_connectors = set()

# Active scheduled tasks
_scheduled_tasks = {}


async def sync_connector(connector_id: str, progress_callback=None) -> dict:
    """
    Run a sync for a single connector, then index any new/changed files.
    Returns the sync result dict.
    """
    if connector_id in _syncing_connectors:
        return {"error": "Sync already in progress for this connector"}

    connector = connector_registry.get_connector(connector_id)
    if not connector:
        return {"error": "Connector not found"}

    _syncing_connectors.add(connector_id)

    try:
        # Run blocking IMAP sync in thread pool
        loop = asyncio.get_event_loop()
        sync_result = await loop.run_in_executor(
            _executor,
            lambda: connector.sync(progress_callback=progress_callback)
        )

        # Index new files after sync
        if sync_result.get("new_items", 0) > 0:
            if progress_callback:
                progress_callback("Indexing new emails...")
            await _index_connector_items(connector, progress_callback)

        return sync_result

    finally:
        _syncing_connectors.discard(connector_id)


async def _index_connector_items(connector, progress_callback=None):
    """
    Index all .txt files in the connector's items folder.
    Uses find_or_create_index to register the folder, then indexes each file.
    """
    items_folder = connector.get_items_folder()
    if not os.path.exists(items_folder):
        return

    # Register this folder as an index (or find existing)
    index_id, index_entry = find_or_create_index(items_folder)

    # Get existing indexed files to detect changes
    existing_files = index_entry.get("files", {})

    txt_files = [f for f in os.listdir(items_folder) if f.endswith(".txt")]
    files_metadata = {}
    indexed_count = 0

    for filename in txt_files:
        filepath = os.path.join(items_folder, filename)
        current_hash = get_file_hash(filepath)

        # Skip if already indexed and unchanged
        if filepath in existing_files and existing_files[filepath].get("hash") == current_hash:
            files_metadata[filepath] = existing_files[filepath]
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if content.strip():
                chunk_count = store_document(filepath, content)
                files_metadata[filepath] = {
                    "hash": current_hash,
                    "chunks": chunk_count,
                    "indexed_at": datetime.now().isoformat(),
                }
                indexed_count += 1
        except Exception as e:
            print(f"Failed to index {filepath}: {e}")

    # Update index metadata
    update_index_metadata(items_folder, files_metadata)

    if progress_callback:
        progress_callback(f"Indexed {indexed_count} new emails")


async def _scheduled_sync(connector_id: str, interval_minutes: int):
    """Background loop: sync a connector on a schedule."""
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            await sync_connector(connector_id)
        except Exception as e:
            print(f"Scheduled sync failed for {connector_id}: {e}")


def start_all_schedules():
    """Start background sync schedules for all configured connectors. Call at startup."""
    connector_registry.restore_all()
    configs = connector_registry.get_all_configs()
    for entry in configs:
        connector_id = entry["id"]
        interval = entry.get("config", {}).get("sync_interval", 30)
        if connector_id not in _scheduled_tasks:
            task = asyncio.create_task(_scheduled_sync(connector_id, interval))
            _scheduled_tasks[connector_id] = task


def stop_all_schedules():
    """Cancel all background sync tasks."""
    for task in _scheduled_tasks.values():
        task.cancel()
    _scheduled_tasks.clear()


def add_schedule(connector_id: str, interval_minutes: int):
    """Add a sync schedule for a newly created connector."""
    if connector_id in _scheduled_tasks:
        _scheduled_tasks[connector_id].cancel()
    task = asyncio.create_task(_scheduled_sync(connector_id, interval_minutes))
    _scheduled_tasks[connector_id] = task


def remove_schedule(connector_id: str):
    """Remove a sync schedule (when connector is deleted)."""
    task = _scheduled_tasks.pop(connector_id, None)
    if task:
        task.cancel()
