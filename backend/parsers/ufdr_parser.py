"""
ufdr_parser.py — Reads uploaded UFDR files and converts them into Python objects.

WHY THIS FILE EXISTS:
  Raw UFDR files come in JSON, CSV, or ZIP format. Before we can store
  or search them, we need to READ and NORMALIZE the data into a consistent
  shape our app understands.

  Think of this like a "universal adapter":
  - Input: messy raw file (could be any format)
  - Output: clean Python dicts with known field names

KEY CONCEPTS:
  - Pydantic models = typed data containers (like TypeScript interfaces)
  - We parse each section (chats, calls, contacts, media) separately
  - We handle missing fields gracefully with defaults
"""

import json
import csv
import zipfile
import io
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


# ── Pydantic Models (data shapes) ─────────────────────────────
# These define what a "clean" parsed record looks like.
# If a field is missing in the raw data, the default kicks in.

class ParsedChat(BaseModel):
    raw_id: str = ""
    platform: str = "Unknown"
    sender: str = "Unknown"
    receiver: str = "Unknown"
    message_text: str = ""
    timestamp: str = ""
    direction: str = "unknown"
    thread_id: str = ""


class ParsedCall(BaseModel):
    raw_id: str = ""
    caller_number: str = ""
    caller_name: str = ""
    receiver_number: str = ""
    receiver_name: str = ""
    timestamp: str = ""
    duration_seconds: int = 0
    call_type: str = "unknown"
    platform: str = "GSM"


class ParsedContact(BaseModel):
    raw_id: str = ""
    name: str = "Unknown"
    phone_numbers: list = []
    email_addresses: list = []
    organization: str = ""
    notes: str = ""


class ParsedMedia(BaseModel):
    raw_id: str = ""
    file_name: str = ""
    file_type: str = ""
    file_size_bytes: int = 0
    timestamp: str = ""
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    source_app: str = ""
    sha256_hash: str = ""


class ParsedCase(BaseModel):
    """The complete parsed output from one UFDR file."""
    case_name: str
    device_info: dict = {}
    chats: list[ParsedChat] = []
    calls: list[ParsedCall] = []
    contacts: list[ParsedContact] = []
    media: list[ParsedMedia] = []
    parse_errors: list[str] = []   # non-fatal errors during parsing


# ── Main Parser Class ─────────────────────────────────────────

class UFDRParser:
    """
    Handles parsing of UFDR-format files.

    Supports:
    - JSON (our synthetic format + Cellebrite JSON exports)
    - ZIP containing JSON/CSV files
    - CSV (flat chat export format)
    """

    def parse_file(self, file_path: str | Path, original_filename: str) -> ParsedCase:
        """
        Main entry point. Detects file type and routes to the right parser.
        Returns a ParsedCase object regardless of input format.
        """
        file_path = Path(file_path)
        filename_lower = original_filename.lower()

        if filename_lower.endswith(".json"):
            return self._parse_json(file_path, original_filename)
        elif filename_lower.endswith(".zip"):
            return self._parse_zip(file_path, original_filename)
        elif filename_lower.endswith(".csv"):
            return self._parse_csv(file_path, original_filename)
        else:
            # Try JSON as default
            return self._parse_json(file_path, original_filename)

    def _parse_json(self, file_path: Path, filename: str) -> ParsedCase:
        """Parse our standard JSON UFDR format."""
        errors = []

        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Extract device info from case_metadata
        meta = raw.get("case_metadata", {})
        device_info = meta.get("device_info", {})
        case_name = meta.get("case_id", filename.replace(".json", ""))

        # Parse each section
        chats = self._parse_chats_json(raw.get("chat_messages", []), errors)
        calls = self._parse_calls_json(raw.get("call_records", []), errors)
        contacts = self._parse_contacts_json(raw.get("contacts", []), errors)
        media = self._parse_media_json(raw.get("media_metadata", []), errors)

        return ParsedCase(
            case_name=case_name,
            device_info=device_info,
            chats=chats,
            calls=calls,
            contacts=contacts,
            media=media,
            parse_errors=errors,
        )

    def _parse_chats_json(self, raw_list: list, errors: list) -> list[ParsedChat]:
        """Parse chat messages from JSON list."""
        chats = []
        for i, item in enumerate(raw_list):
            try:
                # Handle both 'message' and 'message_text' field names
                text = item.get("message") or item.get("message_text") or item.get("text", "")

                # Handle both 'sender_number' and 'sender'
                sender = (
                    item.get("sender_number") or
                    item.get("sender") or
                    item.get("from", "Unknown")
                )
                receiver = (
                    item.get("receiver_number") or
                    item.get("receiver") or
                    item.get("to", "Unknown")
                )

                chats.append(ParsedChat(
                    raw_id=item.get("id", f"MSG_{i}"),
                    platform=item.get("platform", "Unknown"),
                    sender=sender,
                    receiver=receiver,
                    message_text=str(text),
                    timestamp=self._normalize_timestamp(item.get("timestamp", "")),
                    direction=item.get("direction", "unknown"),
                    thread_id=item.get("thread_id", ""),
                ))
            except Exception as e:
                errors.append(f"Chat parse error at index {i}: {str(e)}")

        return chats

    def _parse_calls_json(self, raw_list: list, errors: list) -> list[ParsedCall]:
        """Parse call records from JSON list."""
        calls = []
        for i, item in enumerate(raw_list):
            try:
                calls.append(ParsedCall(
                    raw_id=item.get("id", f"CALL_{i}"),
                    caller_number=item.get("caller_number", ""),
                    caller_name=item.get("caller_name", ""),
                    receiver_number=item.get("receiver_number", ""),
                    receiver_name=item.get("receiver_name", ""),
                    timestamp=self._normalize_timestamp(item.get("timestamp", "")),
                    duration_seconds=int(item.get("duration_seconds", 0)),
                    call_type=item.get("call_type", "unknown"),
                    platform=item.get("platform", "GSM"),
                ))
            except Exception as e:
                errors.append(f"Call parse error at index {i}: {str(e)}")

        return calls

    def _parse_contacts_json(self, raw_list: list, errors: list) -> list[ParsedContact]:
        """Parse contacts from JSON list."""
        contacts = []
        for i, item in enumerate(raw_list):
            try:
                # Phone numbers can be a list or a comma-separated string
                phones = item.get("phone_numbers", [])
                if isinstance(phones, str):
                    phones = [p.strip() for p in phones.split(",") if p.strip()]

                emails = item.get("email_addresses", [])
                if isinstance(emails, str):
                    emails = [emails] if emails else []
                # Handle single "email" field too
                if not emails and item.get("email"):
                    emails = [item["email"]]

                contacts.append(ParsedContact(
                    raw_id=item.get("id", f"CONTACT_{i}"),
                    name=item.get("name", "Unknown"),
                    phone_numbers=phones,
                    email_addresses=emails,
                    organization=item.get("organization", ""),
                    notes=item.get("notes", ""),
                ))
            except Exception as e:
                errors.append(f"Contact parse error at index {i}: {str(e)}")

        return contacts

    def _parse_media_json(self, raw_list: list, errors: list) -> list[ParsedMedia]:
        """Parse media metadata from JSON list."""
        media = []
        for i, item in enumerate(raw_list):
            try:
                media.append(ParsedMedia(
                    raw_id=item.get("id", f"MEDIA_{i}"),
                    file_name=item.get("file_name", ""),
                    file_type=item.get("file_type", ""),
                    file_size_bytes=int(item.get("file_size_bytes", 0)),
                    timestamp=self._normalize_timestamp(item.get("timestamp", "")),
                    gps_latitude=item.get("gps_latitude"),
                    gps_longitude=item.get("gps_longitude"),
                    source_app=item.get("source_app", ""),
                    sha256_hash=item.get("sha256_hash", ""),
                ))
            except Exception as e:
                errors.append(f"Media parse error at index {i}: {str(e)}")

        return media

    def _parse_zip(self, file_path: Path, filename: str) -> ParsedCase:
        """
        Parse a ZIP file containing JSON/CSV exports.
        Many forensic tools export as ZIP with multiple files inside.
        """
        errors = []
        all_chats, all_calls, all_contacts, all_media = [], [], [], []
        device_info = {}
        case_name = filename.replace(".zip", "")

        with zipfile.ZipFile(file_path, "r") as zf:
            for name in zf.namelist():
                with zf.open(name) as inner_file:
                    content = inner_file.read().decode("utf-8", errors="replace")

                    if name.endswith(".json"):
                        try:
                            data = json.loads(content)
                            # If it's our full format
                            if "chat_messages" in data or "case_metadata" in data:
                                # Write to temp file and parse
                                temp_path = file_path.parent / "temp_extracted.json"
                                with open(temp_path, "w") as tf:
                                    tf.write(content)
                                parsed = self._parse_json(temp_path, name)
                                all_chats.extend(parsed.chats)
                                all_calls.extend(parsed.calls)
                                all_contacts.extend(parsed.contacts)
                                all_media.extend(parsed.media)
                                device_info = parsed.device_info
                                temp_path.unlink()
                        except Exception as e:
                            errors.append(f"ZIP JSON error ({name}): {str(e)}")

                    elif name.endswith(".csv"):
                        # Parse as flat chat CSV
                        try:
                            reader = csv.DictReader(io.StringIO(content))
                            for row in reader:
                                all_chats.append(ParsedChat(
                                    raw_id=row.get("id", ""),
                                    platform=row.get("platform", "Unknown"),
                                    sender=row.get("sender", ""),
                                    receiver=row.get("receiver", ""),
                                    message_text=row.get("message", ""),
                                    timestamp=self._normalize_timestamp(row.get("timestamp", "")),
                                ))
                        except Exception as e:
                            errors.append(f"ZIP CSV error ({name}): {str(e)}")

        return ParsedCase(
            case_name=case_name,
            device_info=device_info,
            chats=all_chats,
            calls=all_calls,
            contacts=all_contacts,
            media=all_media,
            parse_errors=errors,
        )

    def _parse_csv(self, file_path: Path, filename: str) -> ParsedCase:
        """Parse a flat CSV file of chat messages."""
        errors = []
        chats = []

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                try:
                    chats.append(ParsedChat(
                        raw_id=row.get("id", f"MSG_{i}"),
                        platform=row.get("platform", "Unknown"),
                        sender=row.get("sender", ""),
                        receiver=row.get("receiver", ""),
                        message_text=row.get("message", row.get("text", "")),
                        timestamp=self._normalize_timestamp(row.get("timestamp", "")),
                        direction=row.get("direction", "unknown"),
                    ))
                except Exception as e:
                    errors.append(f"CSV row {i} error: {str(e)}")

        return ParsedCase(
            case_name=filename.replace(".csv", ""),
            chats=chats,
            parse_errors=errors,
        )

    def _normalize_timestamp(self, ts: str) -> str:
        """
        Try to parse various timestamp formats into ISO 8601.
        Returns the original string if parsing fails (graceful degradation).
        """
        if not ts:
            return ""

        # Already ISO format
        if "T" in ts and len(ts) > 15:
            return ts

        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%Y%m%d%H%M%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(ts, fmt).isoformat()
            except ValueError:
                continue

        return ts   # Return as-is if we can't parse it
