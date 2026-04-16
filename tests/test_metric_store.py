"""Unit tests for MetricStore."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import threading
import time

from rpi_watch.metrics.metric_store import MetricStore


class TestMetricStore(unittest.TestCase):
    """Tests for MetricStore class."""

    def setUp(self):
        """Set up test fixtures."""
        self.store = MetricStore()

    def test_initialization_with_no_value(self):
        """Test store initialization without initial value."""
        self.assertIsNone(self.store.get_latest())
        self.assertFalse(self.store.has_value())

    def test_initialization_with_value(self):
        """Test store initialization with initial value."""
        store = MetricStore(initial_value=42.5)
        self.assertEqual(store.get_latest(), 42.5)
        self.assertTrue(store.has_value())

    def test_initialization_with_payload(self):
        """Test store initialization with initial payload."""
        store = MetricStore(initial_payload={"pm_2_5": "42.5", "status": "ok"})
        self.assertEqual(store.get_payload(), {"pm_2_5": 42.5, "status": "ok"})
        self.assertEqual(store.get_latest(), 42.5)
        self.assertEqual(store.get_selected_field(), "pm_2_5")
        history = store.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["value"], 42.5)
        self.assertEqual(history[0]["field"], "pm_2_5")

    def test_update_value(self):
        """Test updating metric value."""
        self.store.update(23.5)
        self.assertEqual(self.store.get_latest(), 23.5)

    def test_update_converts_to_float(self):
        """Test that update converts values to float."""
        # Update with integer
        self.store.update(42)
        self.assertIsInstance(self.store.get_latest(), float)
        self.assertEqual(self.store.get_latest(), 42.0)

        # Update with string-like number (if supported)
        self.store.update(99.9)
        self.assertEqual(self.store.get_latest(), 99.9)

    def test_get_with_timestamp(self):
        """Test getting value with timestamp."""
        self.store.update(42.5)
        value, timestamp = self.store.get_with_timestamp()

        self.assertEqual(value, 42.5)
        self.assertIsNotNone(timestamp)
        self.assertIsInstance(timestamp, float)

    def test_custom_timestamp(self):
        """Test setting custom timestamp."""
        custom_time = 1000.0
        self.store.update(42.5, timestamp=custom_time)
        value, timestamp = self.store.get_with_timestamp()

        self.assertEqual(value, 42.5)
        self.assertEqual(timestamp, custom_time)

    def test_get_age_seconds(self):
        """Test getting age of metric value."""
        self.store.update(42.5)
        age = self.store.get_age_seconds()

        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0)
        self.assertLess(age, 1)  # Should be very recent

    def test_get_age_seconds_none_when_empty(self):
        """Test that age is None when no value set."""
        age = self.store.get_age_seconds()
        self.assertIsNone(age)

    def test_has_value(self):
        """Test has_value method."""
        self.assertFalse(self.store.has_value())
        self.store.update(42.5)
        self.assertTrue(self.store.has_value())

    def test_update_payload_selects_preferred_field(self):
        """Test payload update with preferred field selection."""
        field, value = self.store.update_payload(
            {"temp": "27.1", "pm_2_5": "8.0", "status": "ok"},
            preferred_field="pm_2_5",
        )
        self.assertEqual(field, "pm_2_5")
        self.assertEqual(value, 8.0)
        self.assertEqual(self.store.get_latest(), 8.0)
        self.assertEqual(self.store.get_selected_field(), "pm_2_5")
        self.assertEqual(
            self.store.get_payload(),
            {"temp": 27.1, "pm_2_5": 8.0, "status": "ok"},
        )

    def test_update_payload_falls_back_to_first_numeric_field(self):
        """Test payload update falls back when no preferred field is available."""
        field, value = self.store.update_payload(
            {"temp": "27.1", "humidity": "47.8"},
            preferred_field="pm_2_5",
        )
        self.assertEqual(field, "temp")
        self.assertEqual(value, 27.1)

    def test_get_numeric_payload(self):
        """Test numeric payload extraction."""
        self.store.update_payload({"temp": "27.1", "humidity": 47.8, "status": "ok"})
        self.assertEqual(
            self.store.get_numeric_payload(),
            {"temp": 27.1, "humidity": 47.8},
        )

    def test_history_keeps_last_n_entries(self):
        """Test bounded history rollover."""
        store = MetricStore(history_size=3)
        for value in (1.0, 2.0, 3.0, 4.0, 5.0):
            store.update(value)

        history = store.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual([entry["value"] for entry in history], [3.0, 4.0, 5.0])

    def test_get_history_limit_returns_latest_entries(self):
        """Test limiting returned history entries."""
        for value in (1.0, 2.0, 3.0, 4.0):
            self.store.update(value)

        history = self.store.get_history(limit=2)
        self.assertEqual([entry["value"] for entry in history], [3.0, 4.0])

    def test_get_field_history(self):
        """Test extracting a field-specific history series."""
        self.store.update_payload(
            {"temp": "27.1", "pm_2_5": "8.0"},
            timestamp=100.0,
            preferred_field="pm_2_5",
        )
        self.store.update_payload(
            {"temp": "26.8", "humidity": "47.8"},
            timestamp=101.0,
            preferred_field="pm_2_5",
        )
        self.store.update_payload(
            {"temp": "26.4", "pm_2_5": "7.4"},
            timestamp=102.0,
            preferred_field="pm_2_5",
        )

        self.assertEqual(
            self.store.get_field_history("pm_2_5"),
            [(100.0, 8.0), (102.0, 7.4)],
        )
        self.assertEqual(
            self.store.get_field_history("temp", limit=2),
            [(101.0, 26.8), (102.0, 26.4)],
        )

    def test_scalar_updates_record_history_without_payload(self):
        """Test scalar-only updates still produce history entries."""
        self.store.update(42.5, timestamp=123.0)
        history = self.store.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["value"], 42.5)
        self.assertIsNone(history[0]["payload"])
        self.assertIsNone(history[0]["field"])

    def test_get_field(self):
        """Test getting a specific field from payload."""
        self.store.update_payload({"temp": "27.1", "humidity": 47.8})
        self.assertEqual(self.store.get_field("temp"), 27.1)
        self.assertEqual(self.store.get_field("humidity"), 47.8)
        self.assertIsNone(self.store.get_field("pm_2_5"))

    def test_select_numeric_field_prefers_previous_field(self):
        """Test field selection reuses prior field when possible."""
        self.store.update_payload({"temp": 27.1, "pm_2_5": 8.0}, preferred_field="pm_2_5")
        field, value = self.store.update_payload({"temp": 26.8, "pm_2_5": 7.4})
        self.assertEqual(field, "pm_2_5")
        self.assertEqual(value, 7.4)

    def test_reset(self):
        """Test resetting the store."""
        self.store.update(42.5)
        self.assertTrue(self.store.has_value())

        self.store.reset()
        self.assertFalse(self.store.has_value())
        self.assertIsNone(self.store.get_latest())
        self.assertIsNone(self.store.get_payload())
        self.assertIsNone(self.store.get_selected_field())
        self.assertEqual(self.store.get_history(), [])

    def test_multiple_updates(self):
        """Test multiple sequential updates."""
        values = [10.0, 20.5, 30.0, 15.5]

        for value in values:
            self.store.update(value)
            self.assertEqual(self.store.get_latest(), value)

    def test_thread_safety(self):
        """Test thread-safe concurrent updates."""
        results = []
        errors = []

        def update_thread(thread_id, value):
            try:
                for i in range(100):
                    self.store.update(value + i * 0.1)
                    # Read immediately to verify
                    current = self.store.get_latest()
                    if current is None:
                        errors.append(f"Thread {thread_id}: Got None value")
                results.append((thread_id, self.store.get_latest()))
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        # Create multiple threads updating concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_thread, args=(i, i * 100))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")

        # Verify final value is set (from last update)
        self.assertIsNotNone(self.store.get_latest())

    def test_thread_safe_read_write(self):
        """Test that reads don't block writes and vice versa."""
        results = {'reads': 0, 'writes': 0}
        errors = []

        def reader_thread():
            try:
                for _ in range(100):
                    self.store.get_latest()
                    self.store.get_with_timestamp()
                    self.store.has_value()
                    results['reads'] += 1
            except Exception as e:
                errors.append(f"Reader: {e}")

        def writer_thread():
            try:
                for i in range(100):
                    self.store.update(float(i))
                    results['writes'] += 1
            except Exception as e:
                errors.append(f"Writer: {e}")

        # Create multiple reader and writer threads
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader_thread))
        for _ in range(2):
            threads.append(threading.Thread(target=writer_thread))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify operations completed
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(results['reads'], 300)  # 3 readers * 100
        self.assertEqual(results['writes'], 200)  # 2 writers * 100

    def test_negative_values(self):
        """Test handling of negative values."""
        self.store.update(-42.5)
        self.assertEqual(self.store.get_latest(), -42.5)

    def test_zero_value(self):
        """Test handling of zero value."""
        self.store.update(0.0)
        self.assertEqual(self.store.get_latest(), 0.0)
        self.assertTrue(self.store.has_value())

    def test_very_large_values(self):
        """Test handling of very large values."""
        large_value = 1.23456e10
        self.store.update(large_value)
        self.assertEqual(self.store.get_latest(), large_value)

    def test_very_small_values(self):
        """Test handling of very small values."""
        small_value = 1.23456e-10
        self.store.update(small_value)
        self.assertAlmostEqual(self.store.get_latest(), small_value, places=15)


if __name__ == '__main__':
    unittest.main()
