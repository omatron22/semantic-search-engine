"""
Gmail/IMAP connector — downloads emails via IMAP and saves them as .txt files.

Uses stdlib only: imaplib + email. Works with any IMAP server (Gmail, Outlook, etc.).
Credentials: { imap_server, email, password }
Incremental sync via UID high-water mark per folder.
"""

import imaplib
import email
from email.header import decode_header
import os
import re
from datetime import datetime

from connectors.base_connector import BaseConnector, ConnectorStatus

MAX_EMAILS_PER_SYNC = 200


def _decode_header_value(value):
    """Decode an email header that may be encoded."""
    if value is None:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def _strip_html(html_text):
    """Basic HTML tag stripping as fallback for HTML-only emails."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_body(msg):
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        plain_parts = []
        html_parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    plain_parts.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                except Exception:
                    pass
            elif content_type == "text/html":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                except Exception:
                    pass
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return _strip_html("\n".join(html_parts))
        return ""
    else:
        content_type = msg.get_content_type()
        try:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            return ""
        if content_type == "text/html":
            return _strip_html(payload)
        return payload


def _safe_filename(text, max_len=80):
    """Convert text to a safe filename."""
    safe = re.sub(r'[^\w\s-]', '', text).strip()
    safe = re.sub(r'\s+', '_', safe)
    return safe[:max_len] if safe else "no_subject"


class GmailConnector(BaseConnector):
    """IMAP-based email connector. Works with Gmail, Outlook, or any IMAP server."""

    FOLDERS = ["INBOX", "[Gmail]/Sent Mail"]

    def __init__(self, connector_id, connector_type, config):
        super().__init__(connector_id, connector_type, config)
        self._imap = None
        self._credentials = None

    def authenticate(self, credentials: dict) -> bool:
        """Validate IMAP credentials by connecting and logging in."""
        required = ["imap_server", "email", "password"]
        for key in required:
            if key not in credentials:
                self.last_error = f"Missing credential: {key}"
                self.status = ConnectorStatus.ERROR
                return False

        try:
            imap = imaplib.IMAP4_SSL(credentials["imap_server"])
            imap.login(credentials["email"], credentials["password"])
            imap.logout()
            self._credentials = credentials
            self.status = ConnectorStatus.AUTHENTICATED
            self.last_error = None
            return True
        except imaplib.IMAP4.error as e:
            self.last_error = f"IMAP auth failed: {e}"
            self.status = ConnectorStatus.ERROR
            return False
        except Exception as e:
            self.last_error = f"Connection failed: {e}"
            self.status = ConnectorStatus.ERROR
            return False

    def sync(self, progress_callback=None) -> dict:
        """
        Incremental sync: fetch emails newer than the last known UID per folder.
        Each email is saved as a .txt file in the items folder.
        """
        if not self._credentials:
            return {"new_items": 0, "total_items": 0, "errors": ["Not authenticated"]}

        self.status = ConnectorStatus.SYNCING
        state = self.load_state()
        uid_watermarks = state.get("uid_watermarks", {})
        items_folder = self.get_items_folder()
        new_items = 0
        errors = []

        try:
            imap = imaplib.IMAP4_SSL(self._credentials["imap_server"])
            imap.login(self._credentials["email"], self._credentials["password"])
        except Exception as e:
            self.status = ConnectorStatus.ERROR
            self.last_error = str(e)
            return {"new_items": 0, "total_items": 0, "errors": [str(e)]}

        try:
            for folder in self.FOLDERS:
                try:
                    status, _ = imap.select(folder, readonly=True)
                    if status != "OK":
                        continue
                except Exception:
                    continue

                if progress_callback:
                    progress_callback(f"Syncing folder: {folder}")

                # Get UIDs above the watermark
                last_uid = uid_watermarks.get(folder, 0)
                search_criteria = f"UID {last_uid + 1}:*"
                status, data = imap.uid("search", None, search_criteria)
                if status != "OK" or not data[0]:
                    continue

                uids = data[0].split()
                # Filter out UIDs <= watermark (IMAP may return the watermark itself)
                uids = [u for u in uids if int(u) > last_uid]

                # Cap per sync
                if len(uids) > MAX_EMAILS_PER_SYNC:
                    uids = uids[:MAX_EMAILS_PER_SYNC]

                max_uid_this_folder = last_uid

                for i, uid_bytes in enumerate(uids):
                    uid = int(uid_bytes)
                    try:
                        status, msg_data = imap.uid("fetch", uid_bytes, "(RFC822)")
                        if status != "OK" or not msg_data[0]:
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        subject = _decode_header_value(msg.get("Subject"))
                        from_addr = _decode_header_value(msg.get("From"))
                        to_addr = _decode_header_value(msg.get("To"))
                        date_str = _decode_header_value(msg.get("Date"))
                        body = _extract_body(msg)

                        # Build .txt content
                        content_lines = [
                            f"Subject: {subject}",
                            f"From: {from_addr}",
                            f"To: {to_addr}",
                            f"Date: {date_str}",
                            f"Folder: {folder}",
                            "",
                            body,
                        ]
                        content = "\n".join(content_lines)

                        # Save as .txt file
                        safe_subj = _safe_filename(subject)
                        filename = f"{uid}_{safe_subj}.txt"
                        filepath = os.path.join(items_folder, filename)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(content)

                        new_items += 1
                        if uid > max_uid_this_folder:
                            max_uid_this_folder = uid

                        if progress_callback and (i + 1) % 10 == 0:
                            progress_callback(f"{folder}: fetched {i + 1}/{len(uids)} emails")

                    except Exception as e:
                        errors.append(f"UID {uid}: {e}")

                uid_watermarks[folder] = max_uid_this_folder

            imap.logout()

        except Exception as e:
            errors.append(str(e))
            self.status = ConnectorStatus.ERROR
            self.last_error = str(e)
            try:
                imap.logout()
            except Exception:
                pass
            return {"new_items": new_items, "total_items": self._count_items(), "errors": errors}

        # Save updated state
        self.last_sync = datetime.now().isoformat()
        self.items_synced = self._count_items()
        self.status = ConnectorStatus.IDLE
        self.last_error = None
        self.save_state({
            "uid_watermarks": uid_watermarks,
            "last_sync": self.last_sync,
            "items_synced": self.items_synced,
        })

        return {
            "new_items": new_items,
            "total_items": self.items_synced,
            "errors": errors,
        }

    def _count_items(self) -> int:
        """Count .txt files in the items folder."""
        folder = self.get_items_folder()
        if not os.path.exists(folder):
            return 0
        return len([f for f in os.listdir(folder) if f.endswith(".txt")])
