"""
Connector registry — manages connector lifecycle, config persistence, and CRUD.

Config is persisted in backend/storage/connectors/connectors_config.json.
"""

import os
import json
import uuid
from datetime import datetime


STORAGE_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "connectors")
CONFIG_FILE = os.path.join(STORAGE_ROOT, "connectors_config.json")

# Registered connector classes: { "gmail": GmailConnector, ... }
_connector_classes = {}

# Live connector instances: { connector_id: instance }
_connector_instances = {}


def register(type_name: str, cls):
    """Register a connector class by type name."""
    _connector_classes[type_name] = cls


def get_available_types() -> list:
    """Return list of registered connector type names."""
    return list(_connector_classes.keys())


def _load_config() -> dict:
    """Load persisted connector config from disk."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"connectors": []}


def _save_config(config: dict):
    """Save connector config to disk."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def _instantiate(entry: dict):
    """Create a connector instance from a config entry."""
    cls = _connector_classes.get(entry["type"])
    if not cls:
        return None
    instance = cls(
        connector_id=entry["id"],
        connector_type=entry["type"],
        config=entry.get("config", {}),
    )
    # Restore credentials (already validated when added)
    creds = entry.get("credentials", {})
    if creds:
        try:
            instance.authenticate(creds)
        except Exception:
            from connectors.base_connector import ConnectorStatus
            instance.status = ConnectorStatus.ERROR
            instance.last_error = "Failed to re-authenticate on startup"
    # Restore state
    state = instance.load_state()
    if state.get("last_sync"):
        instance.last_sync = state["last_sync"]
    if state.get("items_synced"):
        instance.items_synced = state["items_synced"]
    return instance


def add_connector(connector_type: str, credentials: dict, label: str = "", sync_interval: int = 30) -> dict:
    """
    Create a new connector, authenticate it, persist config.
    Returns the connector status dict or raises ValueError.
    """
    if connector_type not in _connector_classes:
        raise ValueError(f"Unknown connector type: {connector_type}")

    connector_id = uuid.uuid4().hex[:12]
    config = {
        "label": label or connector_type,
        "sync_interval": sync_interval,
    }

    cls = _connector_classes[connector_type]
    instance = cls(
        connector_id=connector_id,
        connector_type=connector_type,
        config=config,
    )

    # Authenticate
    if not instance.authenticate(credentials):
        raise ValueError("Authentication failed — check credentials")

    # Persist config
    cfg = _load_config()
    cfg["connectors"].append({
        "id": connector_id,
        "type": connector_type,
        "label": label or connector_type,
        "credentials": credentials,
        "config": config,
        "added_at": datetime.now().isoformat(),
    })
    _save_config(cfg)

    # Store live instance
    _connector_instances[connector_id] = instance
    return instance.get_status()


def get_connector(connector_id: str):
    """Get a live connector instance (lazy-instantiate from config if needed)."""
    if connector_id in _connector_instances:
        return _connector_instances[connector_id]

    # Try to instantiate from config
    cfg = _load_config()
    for entry in cfg["connectors"]:
        if entry["id"] == connector_id:
            instance = _instantiate(entry)
            if instance:
                _connector_instances[connector_id] = instance
            return instance
    return None


def list_connectors() -> list:
    """Return status of all configured connectors."""
    cfg = _load_config()
    results = []
    for entry in cfg["connectors"]:
        instance = get_connector(entry["id"])
        if instance:
            results.append(instance.get_status())
        else:
            results.append({
                "connector_id": entry["id"],
                "connector_type": entry["type"],
                "label": entry.get("label", entry["type"]),
                "status": "error",
                "last_error": "Could not instantiate connector",
            })
    return results


def remove_connector(connector_id: str) -> bool:
    """Remove a connector: cleanup files, remove from config."""
    instance = get_connector(connector_id)
    items_folder = None
    if instance:
        items_folder = instance.get_items_folder()
        instance.cleanup()

    # Remove from config
    cfg = _load_config()
    cfg["connectors"] = [c for c in cfg["connectors"] if c["id"] != connector_id]
    _save_config(cfg)

    # Remove live instance
    _connector_instances.pop(connector_id, None)

    return items_folder


def get_all_configs() -> list:
    """Return raw config entries (for sync engine scheduling)."""
    return _load_config()["connectors"]


def restore_all():
    """Re-instantiate all connectors from persisted config (called at startup)."""
    cfg = _load_config()
    for entry in cfg["connectors"]:
        if entry["id"] not in _connector_instances:
            instance = _instantiate(entry)
            if instance:
                _connector_instances[entry["id"]] = instance
