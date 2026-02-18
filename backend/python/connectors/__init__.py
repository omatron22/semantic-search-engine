"""
Connectors package — register all available connector types at import time.
"""

from connectors.connector_registry import register
from connectors.gmail_connector import GmailConnector

# Register connectors
register("gmail", GmailConnector)
