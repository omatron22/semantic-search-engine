"""
Abstract base class for all data source connectors.

Each connector pulls data from an external source (email, cloud storage, etc.)
and saves it as local .txt files that the existing indexing pipeline processes.
"""

import os
import json
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime


class ConnectorStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"
    AUTHENTICATED = "authenticated"
    NOT_CONFIGURED = "not_configured"


STORAGE_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "connectors")


class BaseConnector(ABC):
    """Abstract base class all connectors must extend."""

    def __init__(self, connector_id: str, connector_type: str, config: dict):
        self.connector_id = connector_id
        self.connector_type = connector_type
        self.config = config
        self.label = config.get("label", connector_type)
        self.status = ConnectorStatus.NOT_CONFIGURED
        self.last_sync = None
        self.last_error = None
        self.items_synced = 0

        # Ensure storage directories exist
        os.makedirs(self.get_items_folder(), exist_ok=True)
        os.makedirs(self._state_dir(), exist_ok=True)

    def _base_dir(self) -> str:
        return os.path.join(STORAGE_ROOT, self.connector_type, self.connector_id)

    def _state_dir(self) -> str:
        return self._base_dir()

    def get_items_folder(self) -> str:
        """Path to the directory where .txt files are stored for indexing."""
        return os.path.join(self._base_dir(), "items")

    def _state_file(self) -> str:
        return os.path.join(self._state_dir(), "state.json")

    def load_state(self) -> dict:
        """Load persisted sync state (e.g., last UID)."""
        path = self._state_file()
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {}

    def save_state(self, state: dict):
        """Persist sync state to disk."""
        with open(self._state_file(), "w") as f:
            json.dump(state, f, indent=2)

    @abstractmethod
    def authenticate(self, credentials: dict) -> bool:
        """Validate credentials. Returns True if successful."""
        pass

    @abstractmethod
    def sync(self, progress_callback=None) -> dict:
        """
        Pull new items from the source and save as .txt files.
        Returns dict with keys: new_items, total_items, errors.
        progress_callback(message: str) is called with status updates.
        """
        pass

    def get_status(self) -> dict:
        """Return current connector status as a dict."""
        return {
            "connector_id": self.connector_id,
            "connector_type": self.connector_type,
            "label": self.label,
            "status": self.status.value,
            "last_sync": self.last_sync,
            "last_error": self.last_error,
            "items_synced": self.items_synced,
            "items_folder": self.get_items_folder(),
        }

    def cleanup(self):
        """Delete all local data for this connector."""
        import shutil
        base = self._base_dir()
        if os.path.exists(base):
            shutil.rmtree(base)
