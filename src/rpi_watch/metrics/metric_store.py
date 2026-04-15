"""Thread-safe storage for metric values.

Provides synchronized access to the latest metric value received from MQTT
with timestamp tracking.
"""

import logging
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class MetricStore:
    """Thread-safe storage for metric values with timestamp tracking."""

    def __init__(self, initial_value: Optional[float] = None):
        """Initialize metric store.

        Args:
            initial_value: Optional initial metric value
        """
        self._lock = threading.RLock()  # Re-entrant lock
        self._value = initial_value
        self._timestamp = time.time() if initial_value is not None else None
        logger.info(f"MetricStore initialized with value={initial_value}")

    def update(self, value: float, timestamp: Optional[float] = None) -> None:
        """Update the stored metric value.

        Thread-safe update operation.

        Args:
            value: New metric value
            timestamp: Optional timestamp. If None, uses current time.
        """
        with self._lock:
            self._value = float(value)
            self._timestamp = timestamp if timestamp is not None else time.time()
            logger.debug(f"Metric updated: value={self._value}, timestamp={self._timestamp}")

    def get_latest(self) -> Optional[float]:
        """Get the most recent metric value.

        Returns:
            Float value or None if never updated
        """
        with self._lock:
            return self._value

    def get_with_timestamp(self) -> Tuple[Optional[float], Optional[float]]:
        """Get the metric value along with timestamp.

        Returns:
            Tuple of (value, timestamp) or (None, None) if never updated
        """
        with self._lock:
            return (self._value, self._timestamp)

    def get_age_seconds(self) -> Optional[float]:
        """Get age of the current metric value in seconds.

        Returns:
            Age in seconds, or None if no value set
        """
        with self._lock:
            if self._timestamp is None:
                return None
            return time.time() - self._timestamp

    def has_value(self) -> bool:
        """Check if a metric value has been set.

        Returns:
            True if value exists, False otherwise
        """
        with self._lock:
            return self._value is not None

    def reset(self) -> None:
        """Reset the metric store to initial state."""
        with self._lock:
            self._value = None
            self._timestamp = None
            logger.info("Metric store reset")
