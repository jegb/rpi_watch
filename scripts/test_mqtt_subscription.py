#!/usr/bin/env python3
"""Standalone MQTT connectivity/subscription probe.

Checks three layers independently:
1. TCP reachability to the broker host/port
2. MQTT connection establishment
3. First parsed metric received on the configured topic
"""

import argparse
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rpi_watch.metrics import MetricStore
from rpi_watch.mqtt import MQTTSubscriber
from rpi_watch.utils import setup_logging

import logging

logger = logging.getLogger(__name__)


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def _load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe MQTT connectivity and wait for the first metric update.",
    )
    parser.add_argument(
        "--config",
        default=str(_default_config_path()),
        help="Path to YAML config file",
    )
    parser.add_argument("--broker-host", help="Override broker host from config")
    parser.add_argument("--broker-port", type=int, help="Override broker port from config")
    parser.add_argument("--topic", help="Override MQTT topic from config")
    parser.add_argument("--qos", type=int, help="Override QoS from config")
    parser.add_argument("--keepalive", type=int, help="Override keepalive from config")
    parser.add_argument(
        "--json-field",
        help="Optional JSON field to extract from payload",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for MQTT connect + first message",
    )
    parser.add_argument(
        "--socket-timeout",
        type=float,
        default=3.0,
        help="Seconds for the initial TCP reachability check",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.1,
        help="Polling interval while waiting for connection/message",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args()


def _resolve_mqtt_config(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    mqtt_config = config.get("mqtt", {})
    return {
        "broker_host": args.broker_host or mqtt_config.get("broker_host", "localhost"),
        "broker_port": args.broker_port or mqtt_config.get("broker_port", 1883),
        "topic": args.topic or mqtt_config.get("topic", "sensor/metric"),
        "qos": args.qos if args.qos is not None else mqtt_config.get("qos", 1),
        "keepalive": args.keepalive if args.keepalive is not None else mqtt_config.get("keepalive", 60),
        "json_field": (
            args.json_field if args.json_field is not None else mqtt_config.get("json_field")
        ),
    }


def _probe_tcp(host: str, port: int, timeout: float) -> Optional[str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return None
    except OSError as exc:
        return str(exc)


def main() -> int:
    args = _parse_args()
    setup_logging(level=args.log_level)

    config_path = Path(args.config)
    config = _load_config(config_path)
    mqtt_config = _resolve_mqtt_config(config, args)

    logger.info(f"Config: {config_path}")
    logger.info(
        "Probing MQTT broker=%s:%s topic=%s qos=%s json_field=%s",
        mqtt_config["broker_host"],
        mqtt_config["broker_port"],
        mqtt_config["topic"],
        mqtt_config["qos"],
        mqtt_config["json_field"],
    )

    tcp_error = _probe_tcp(
        mqtt_config["broker_host"],
        mqtt_config["broker_port"],
        args.socket_timeout,
    )
    if tcp_error is not None:
        logger.error(
            "TCP reachability check failed for %s:%s: %s",
            mqtt_config["broker_host"],
            mqtt_config["broker_port"],
            tcp_error,
        )
        return 2

    logger.info(
        "TCP reachability check passed for %s:%s",
        mqtt_config["broker_host"],
        mqtt_config["broker_port"],
    )

    metric_store = MetricStore()
    subscriber = MQTTSubscriber(
        broker_host=mqtt_config["broker_host"],
        broker_port=mqtt_config["broker_port"],
        topic=mqtt_config["topic"],
        qos=mqtt_config["qos"],
        keepalive=mqtt_config["keepalive"],
        metric_store=metric_store,
        json_field=mqtt_config["json_field"],
    )

    try:
        subscriber.start()
    except Exception as exc:
        logger.error(f"MQTT start failed: {exc}")
        return 3

    connected_logged = False
    deadline = time.monotonic() + args.timeout

    try:
        while time.monotonic() < deadline:
            if subscriber.is_connected() and not connected_logged:
                logger.info("MQTT connection established; waiting for first message...")
                connected_logged = True

            value, timestamp = metric_store.get_with_timestamp()
            if value is not None:
                age_seconds = 0.0 if timestamp is None else max(0.0, time.time() - timestamp)
                logger.info(
                    "Received metric %.3f on %s (age %.3fs)",
                    value,
                    mqtt_config["topic"],
                    age_seconds,
                )
                return 0

            time.sleep(args.poll_interval)

        if connected_logged:
            logger.warning(
                "Connected to broker, but no matching messages were received on %s within %.1fs",
                mqtt_config["topic"],
                args.timeout,
            )
            return 4

        logger.warning(
            "TCP was reachable, but MQTT never reached connected state within %.1fs",
            args.timeout,
        )
        return 5
    finally:
        try:
            subscriber.stop()
        except Exception as exc:
            logger.warning(f"Failed to stop MQTT subscriber cleanly: {exc}")


if __name__ == "__main__":
    sys.exit(main())
