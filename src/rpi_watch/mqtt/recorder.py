"""Append-only MQTT receive log for later extraction and training."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_RESERVED_FIELDS = {
    "received_at",
    "received_at_iso",
    "mqtt_topic",
    "message_type",
    "message_value",
    "selected_field",
    "selected_value",
    "raw_payload",
}


class MQTTRecordLogger:
    """Append received MQTT messages to a JSONL file."""

    def __init__(self, record_path: str):
        self.path = Path(record_path).expanduser()
        self._lock = threading.RLock()

    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        """Return an ISO-8601 UTC timestamp string."""
        return (
            datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _normalize_field_name(name: str) -> str:
        """Avoid collisions between metadata and payload field names."""
        if name in _RESERVED_FIELDS:
            return f"payload_{name}"
        return name

    def build_record(
        self,
        *,
        topic: str,
        received_at: float,
        raw_payload: str,
        payload: Any,
        selected_field: Optional[str],
        selected_value: Optional[float],
    ) -> dict[str, Any]:
        """Build a JSON-serializable log record."""
        record: dict[str, Any] = {
            "received_at": float(received_at),
            "received_at_iso": self._format_timestamp(received_at),
            "mqtt_topic": topic,
            "selected_field": selected_field,
            "selected_value": selected_value,
            "raw_payload": raw_payload,
        }

        if isinstance(payload, dict):
            record["message_type"] = "json_object"
            for key, value in payload.items():
                record[self._normalize_field_name(str(key))] = value
        else:
            record["message_type"] = "scalar"
            record["message_value"] = payload

        return record

    def append(
        self,
        *,
        topic: str,
        received_at: float,
        raw_payload: str,
        payload: Any,
        selected_field: Optional[str],
        selected_value: Optional[float],
    ) -> None:
        """Append a single JSONL record to disk."""
        record = self.build_record(
            topic=topic,
            received_at=received_at,
            raw_payload=raw_payload,
            payload=payload,
            selected_field=selected_field,
            selected_value=selected_value,
        )

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
                handle.flush()

        logger.debug("Recorded MQTT message to %s", self.path)
