"""
Centralized configuration for Coffee search engine.
Reads/writes storage/engine_config.json.
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "storage", "engine_config.json")

# Model configurations: name -> {table_name, dimensions}
MODELS = {
    "all-MiniLM-L6-v2": {
        "table_name": "documents_v2",
        "dimensions": 384,
    },
    "all-mpnet-base-v2": {
        "table_name": "documents_mpnet",
        "dimensions": 768,
    },
}

DEFAULTS = {
    "embedding_model": "all-MiniLM-L6-v2",
    "engine_version": 2,
    "features": {
        "chunking": True,
        "reranker": True,
        "query_expansion": True,
        "hybrid_search": True,
    },
}


def _load_config():
    """Load config from disk, or return defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULTS)


def _save_config(config):
    """Write config to disk."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_embedding_model():
    """Return the current embedding model name."""
    return _load_config().get("embedding_model", DEFAULTS["embedding_model"])


def get_table_name():
    """Return the LanceDB table name for the current model."""
    model = get_embedding_model()
    return MODELS.get(model, MODELS["all-MiniLM-L6-v2"])["table_name"]


def get_dimensions():
    """Return embedding dimensions for the current model."""
    model = get_embedding_model()
    return MODELS.get(model, MODELS["all-MiniLM-L6-v2"])["dimensions"]


def get_engine_version():
    """Return the current engine version."""
    return _load_config().get("engine_version", DEFAULTS["engine_version"])


def get_feature_flags():
    """Return feature flags dict."""
    config = _load_config()
    return config.get("features", DEFAULTS["features"])


def is_feature_enabled(feature_name):
    """Check if a specific feature is enabled."""
    flags = get_feature_flags()
    return flags.get(feature_name, False)


def needs_reindex():
    """Check if a reindex is needed (config version vs stored version)."""
    config = _load_config()
    stored_version = config.get("last_indexed_version", 0)
    return stored_version < DEFAULTS["engine_version"]


def mark_reindex_complete():
    """Mark that reindexing has been done for the current engine version."""
    config = _load_config()
    config["last_indexed_version"] = DEFAULTS["engine_version"]
    _save_config(config)


def init_config():
    """Initialize config file if it doesn't exist."""
    if not os.path.exists(CONFIG_PATH):
        _save_config(DEFAULTS)
    return _load_config()
