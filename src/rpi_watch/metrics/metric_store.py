"""Thread-safe storage for metric values, payload snapshots, and recent history."""

from collections import deque
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


class MetricStore:
    """Thread-safe storage for metric values and payloads with timestamps."""

    def __init__(
        self,
        initial_value: Optional[float] = None,
        initial_payload: Optional[dict[str, Any]] = None,
        history_size: int = 50,
        persist_path: Optional[str] = None,
    ):
        """Initialize metric store.

        Args:
            initial_value: Optional initial metric value
            initial_payload: Optional initial payload snapshot
            history_size: Maximum number of recent readings to retain
            persist_path: Optional JSON cache path used to persist and restore state
        """
        self._lock = threading.RLock()
        self._history = deque(maxlen=max(1, int(history_size)))
        self._persist_path = Path(persist_path).expanduser() if persist_path else None
        self._payload = self.normalize_payload(initial_payload) if initial_payload else None
        self._selected_field = None
        if initial_payload:
            self._selected_field, selected_value = self.select_numeric_field(self._payload)
            self._value = selected_value if initial_value is None else initial_value
        else:
            self._value = initial_value
        self._timestamp = time.time() if self._value is not None or self._payload else None
        if self._timestamp is not None:
            self._append_history_entry(
                value=self._value,
                timestamp=self._timestamp,
                payload=self._payload,
                field=self._selected_field,
            )
        elif self._persist_path is not None:
            self._restore_persisted_state()
        logger.info(
            f"MetricStore initialized with value={initial_value}, "
            f"payload_keys={list(self._payload.keys()) if self._payload else None}, "
            f"history_size={self._history.maxlen}, "
            f"persist_path={str(self._persist_path) if self._persist_path else None}"
        )

    @staticmethod
    def _copy_payload(payload: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Return a shallow copy of a payload snapshot."""
        if payload is None:
            return None
        return dict(payload)

    @classmethod
    def _copy_history_entry(cls, entry: dict[str, Any]) -> dict[str, Any]:
        """Return a defensive copy of a history entry."""
        return {
            "timestamp": entry["timestamp"],
            "value": entry["value"],
            "field": entry["field"],
            "payload": cls._copy_payload(entry["payload"]),
        }

    def _append_history_entry(
        self,
        *,
        value: Optional[float],
        timestamp: float,
        payload: Optional[dict[str, Any]],
        field: Optional[str],
    ) -> None:
        """Append a new reading snapshot to bounded history."""
        self._history.append(
            {
                "timestamp": timestamp,
                "value": value,
                "field": field,
                "payload": self._copy_payload(payload),
            }
        )

    def _serialize_state_locked(self) -> dict[str, Any]:
        """Serialize current state for persistence."""
        return {
            "value": self._value,
            "timestamp": self._timestamp,
            "selected_field": self._selected_field,
            "payload": self._copy_payload(self._payload),
            "history": [self._copy_history_entry(entry) for entry in self._history],
        }

    def _persist_state_locked(self) -> None:
        """Persist current state to disk."""
        if self._persist_path is None:
            return

        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._persist_path.with_suffix(f"{self._persist_path.suffix}.tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(self._serialize_state_locked(), handle, ensure_ascii=False)
            temp_path.replace(self._persist_path)
        except Exception as exc:
            logger.warning("Failed to persist metric store state to %s: %s", self._persist_path, exc)

    def _restore_persisted_state(self) -> None:
        """Restore state from disk if a cache file exists."""
        if self._persist_path is None or not self._persist_path.exists():
            return

        try:
            with self._persist_path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except Exception as exc:
            logger.warning("Failed to read metric store cache from %s: %s", self._persist_path, exc)
            return

        with self._lock:
            self._value = None
            self._payload = None
            self._timestamp = None
            self._selected_field = None
            self._history.clear()

            payload = state.get("payload")
            self._payload = self.normalize_payload(payload) if isinstance(payload, dict) else None

            selected_field = state.get("selected_field")
            self._selected_field = str(selected_field) if selected_field is not None else None

            timestamp = state.get("timestamp")
            try:
                self._timestamp = float(timestamp) if timestamp is not None else None
            except (TypeError, ValueError):
                self._timestamp = None

            value = state.get("value")
            try:
                self._value = self._coerce_numeric(value) if value is not None else None
            except (TypeError, ValueError):
                self._value = None

            history_entries = state.get("history")
            if isinstance(history_entries, list):
                for raw_entry in history_entries[-self._history.maxlen:]:
                    if not isinstance(raw_entry, dict):
                        continue

                    entry_timestamp = raw_entry.get("timestamp")
                    try:
                        entry_timestamp = float(entry_timestamp)
                    except (TypeError, ValueError):
                        continue

                    entry_value = raw_entry.get("value")
                    try:
                        entry_value = self._coerce_numeric(entry_value) if entry_value is not None else None
                    except (TypeError, ValueError):
                        entry_value = None

                    entry_field = raw_entry.get("field")
                    if entry_field is not None:
                        entry_field = str(entry_field)

                    entry_payload = raw_entry.get("payload")
                    if isinstance(entry_payload, dict):
                        entry_payload = self.normalize_payload(entry_payload)
                    else:
                        entry_payload = None

                    self._append_history_entry(
                        value=entry_value,
                        timestamp=entry_timestamp,
                        payload=entry_payload,
                        field=entry_field,
                    )

            if self._payload is None and self._history:
                latest_entry = self._history[-1]
                self._payload = self._copy_payload(latest_entry["payload"])
                if self._value is None:
                    self._value = latest_entry["value"]
                if self._selected_field is None:
                    self._selected_field = latest_entry["field"]
                if self._timestamp is None:
                    self._timestamp = latest_entry["timestamp"]

        logger.info(
            "Restored metric store state from %s (value=%s, field=%s, history=%s)",
            self._persist_path,
            self._value,
            self._selected_field,
            len(self._history),
        )

    @staticmethod
    def _coerce_numeric(value: Any) -> float:
        """Convert a numeric-like value to float."""
        if isinstance(value, bool):
            raise TypeError("bool is not treated as a metric value")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("empty string")
            return float(stripped)
        raise TypeError(f"Unsupported numeric type: {type(value)!r}")

    @classmethod
    def normalize_payload(cls, payload: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Normalize a payload by converting numeric-like values to floats."""
        if payload is None:
            return None

        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            try:
                normalized[key] = cls._coerce_numeric(value)
            except (TypeError, ValueError):
                normalized[key] = value
        return normalized

    @classmethod
    def extract_numeric_payload(cls, payload: Optional[dict[str, Any]]) -> dict[str, float]:
        """Return only numeric fields from a payload."""
        if not payload:
            return {}

        numeric_payload: dict[str, float] = {}
        for key, value in payload.items():
            try:
                numeric_payload[key] = cls._coerce_numeric(value)
            except (TypeError, ValueError):
                continue
        return numeric_payload

    @classmethod
    def select_numeric_field(
        cls,
        payload: Optional[dict[str, Any]],
        preferred_field: Optional[str] = None,
        previous_field: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[float]]:
        """Select a numeric field from a payload.

        Selection order:
        1. preferred_field if present and numeric
        2. previous_field if present and numeric
        3. ``value`` if present and numeric
        4. first numeric field in payload order
        """
        numeric_payload = cls.extract_numeric_payload(payload)
        if not numeric_payload:
            return (None, None)

        for field_name in (preferred_field, previous_field, "value"):
            if field_name and field_name in numeric_payload:
                return (field_name, numeric_payload[field_name])

        first_key = next(iter(numeric_payload))
        return (first_key, numeric_payload[first_key])

    def update(
        self,
        value: float,
        timestamp: Optional[float] = None,
        payload: Optional[dict[str, Any]] = None,
        source_field: Optional[str] = None,
    ) -> None:
        """Update the stored metric value.

        Args:
            value: New metric value
            timestamp: Optional timestamp. If None, uses current time.
            payload: Optional payload snapshot associated with the value
            source_field: Optional payload field name used to derive the value
        """
        normalized_payload = self.normalize_payload(payload) if payload is not None else None
        with self._lock:
            self._value = float(value)
            if normalized_payload is not None:
                self._payload = normalized_payload
            if source_field is not None:
                self._selected_field = source_field
            self._timestamp = timestamp if timestamp is not None else time.time()
            self._append_history_entry(
                value=self._value,
                timestamp=self._timestamp,
                payload=normalized_payload,
                field=source_field,
            )
            logger.debug(
                f"Metric updated: value={self._value}, field={self._selected_field}, "
                f"timestamp={self._timestamp}"
            )
            self._persist_state_locked()

    def update_payload(
        self,
        payload: dict[str, Any],
        timestamp: Optional[float] = None,
        preferred_field: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[float]]:
        """Update the store with a full payload snapshot."""
        normalized_payload = self.normalize_payload(payload)

        with self._lock:
            selected_field, selected_value = self.select_numeric_field(
                normalized_payload,
                preferred_field=preferred_field,
                previous_field=self._selected_field,
            )
            self._payload = normalized_payload
            self._timestamp = timestamp if timestamp is not None else time.time()
            self._selected_field = selected_field
            self._value = selected_value
            self._append_history_entry(
                value=self._value,
                timestamp=self._timestamp,
                payload=self._payload,
                field=self._selected_field,
            )
            logger.debug(
                f"Payload updated: selected_field={selected_field}, "
                f"selected_value={selected_value}, timestamp={self._timestamp}"
            )
            self._persist_state_locked()

        return (selected_field, selected_value)

    def get_latest(self) -> Optional[float]:
        """Get the most recent selected metric value."""
        with self._lock:
            return self._value

    def get_with_timestamp(self) -> Tuple[Optional[float], Optional[float]]:
        """Get the metric value along with timestamp."""
        with self._lock:
            return (self._value, self._timestamp)

    def get_payload(self) -> Optional[dict[str, Any]]:
        """Get the most recent payload snapshot."""
        with self._lock:
            return self._copy_payload(self._payload)

    def get_numeric_payload(self) -> dict[str, float]:
        """Get numeric payload fields only."""
        with self._lock:
            return self.extract_numeric_payload(self._payload)

    def get_history(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        """Get recent reading snapshots in chronological order."""
        with self._lock:
            history = list(self._history)

        if limit is not None:
            if limit <= 0:
                return []
            history = history[-limit:]

        return [self._copy_history_entry(entry) for entry in history]

    def get_field_history(
        self,
        field_name: str,
        limit: Optional[int] = None,
    ) -> list[tuple[float, float]]:
        """Get a time series for a specific numeric field."""
        series: list[tuple[float, float]] = []
        for entry in self.get_history(limit=limit):
            payload = entry["payload"]
            if payload is not None and field_name in payload:
                try:
                    series.append((entry["timestamp"], self._coerce_numeric(payload[field_name])))
                except (TypeError, ValueError):
                    continue
            elif entry["field"] == field_name and entry["value"] is not None:
                series.append((entry["timestamp"], float(entry["value"])))
        return series

    def get_field(self, field_name: str) -> Optional[float]:
        """Get a single numeric field from the current payload."""
        with self._lock:
            if self._payload is None:
                return None
            try:
                return self._coerce_numeric(self._payload[field_name])
            except (KeyError, TypeError, ValueError):
                return None

    def get_selected_field(self) -> Optional[str]:
        """Get the field associated with the latest selected metric value."""
        with self._lock:
            return self._selected_field

    def get_age_seconds(self) -> Optional[float]:
        """Get age of the current metric value in seconds."""
        with self._lock:
            if self._timestamp is None:
                return None
            return time.time() - self._timestamp

    def has_value(self) -> bool:
        """Check if a metric value has been set."""
        with self._lock:
            return self._value is not None

    def reset(self) -> None:
        """Reset the metric store to initial state."""
        with self._lock:
            self._value = None
            self._payload = None
            self._timestamp = None
            self._selected_field = None
            self._history.clear()
            if self._persist_path is not None:
                try:
                    self._persist_path.unlink(missing_ok=True)
                except Exception as exc:
                    logger.warning("Failed to remove metric store cache %s: %s", self._persist_path, exc)
            logger.info("Metric store reset")
