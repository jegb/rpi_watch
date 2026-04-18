"""Unit tests for MQTT receive log persistence."""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rpi_watch.metrics.metric_store import MetricStore
from rpi_watch.mqtt.recorder import MQTTRecordLogger
import rpi_watch.mqtt.subscriber as subscriber_module
from rpi_watch.mqtt.subscriber import MQTTSubscriber


class _FakeMQTTModule:
    """Minimal paho-mqtt stub for subscriber construction."""

    class CallbackAPIVersion:
        VERSION1 = object()

    class Client:
        def __init__(self, *_args, **_kwargs):
            self.on_connect = None
            self.on_message = None
            self.on_disconnect = None
            self.on_subscribe = None
            self._socket_connect_timeout = None


class TestMQTTRecordLogger(unittest.TestCase):
    """Tests for the append-only MQTT training log."""

    def test_build_record_flattens_payload_and_keeps_metadata(self):
        """JSONL records should be easy to load for later training."""
        logger = MQTTRecordLogger("/tmp/unused.jsonl")
        record = logger.build_record(
            topic="airquality/sensor",
            received_at=1713436800.25,
            raw_payload='{"pm_2_5":11.9,"temp":26.2}',
            payload={"pm_2_5": 11.9, "temp": 26.2},
            selected_field="pm_2_5",
            selected_value=11.9,
        )

        self.assertEqual(record["mqtt_topic"], "airquality/sensor")
        self.assertEqual(record["selected_field"], "pm_2_5")
        self.assertEqual(record["selected_value"], 11.9)
        self.assertEqual(record["pm_2_5"], 11.9)
        self.assertEqual(record["temp"], 26.2)
        self.assertEqual(record["raw_payload"], '{"pm_2_5":11.9,"temp":26.2}')
        self.assertTrue(record["received_at_iso"].endswith("Z"))

    def test_append_writes_jsonl_row(self):
        """Appender should create parent directories and write one record per line."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "data" / "mqtt_records.jsonl"
            logger = MQTTRecordLogger(str(output_path))
            logger.append(
                topic="airquality/sensor",
                received_at=1713436800.25,
                raw_payload='{"pm_2_5":11.9}',
                payload={"pm_2_5": 11.9},
                selected_field="pm_2_5",
                selected_value=11.9,
            )

            rows = output_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(rows), 1)
            written = json.loads(rows[0])
            self.assertEqual(written["pm_2_5"], 11.9)
            self.assertEqual(written["mqtt_topic"], "airquality/sensor")


class TestMQTTSubscriberRecording(unittest.TestCase):
    """Tests for subscriber-side receive log integration."""

    def setUp(self):
        self.original_mqtt = subscriber_module.mqtt
        subscriber_module.mqtt = _FakeMQTTModule

    def tearDown(self):
        subscriber_module.mqtt = self.original_mqtt

    def test_message_is_appended_to_record_log(self):
        """Decoded MQTT payloads should be persisted alongside MetricStore updates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            record_path = Path(temp_dir) / "mqtt_records.jsonl"
            subscriber = MQTTSubscriber(
                broker_host="127.0.0.1",
                topic="airquality/sensor",
                metric_store=MetricStore(),
                json_field="pm_2_5",
                record_path=str(record_path),
            )

            message = SimpleNamespace(
                topic="airquality/sensor",
                payload=b'{"pm_1_0":4.2,"pm_2_5":11.9,"temp":26.2,"humidity":46.2}',
            )

            subscriber._on_message(None, None, message)

            rows = record_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(rows), 1)

            record = json.loads(rows[0])
            self.assertEqual(record["mqtt_topic"], "airquality/sensor")
            self.assertEqual(record["selected_field"], "pm_2_5")
            self.assertEqual(record["selected_value"], 11.9)
            self.assertEqual(record["pm_1_0"], 4.2)
            self.assertEqual(record["pm_2_5"], 11.9)
            self.assertEqual(record["temp"], 26.2)
            self.assertEqual(record["humidity"], 46.2)
            self.assertTrue(record["received_at_iso"].endswith("Z"))
