"""MQTT subscriber for receiving metric updates from broker.

Handles connection to MQTT broker, message parsing, and thread-safe metric updates.
"""

import json
import logging
import threading
import time
import warnings
from typing import Callable, Optional

# Suppress paho-mqtt deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    """Non-blocking MQTT subscriber for metric updates.

    Maintains connection to MQTT broker and updates metric_store
    as new values arrive via callbacks.
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        topic: str = "sensor/metric",
        qos: int = 1,
        keepalive: int = 60,
        metric_store=None,
        json_field: Optional[str] = None,
    ):
        """Initialize MQTT subscriber.

        Args:
            broker_host: MQTT broker hostname or IP address
            broker_port: MQTT broker port (default 1883)
            topic: MQTT topic to subscribe to
            qos: Quality of Service level (0, 1, or 2)
            keepalive: Seconds between keepalive pings
            metric_store: MetricStore object for storing received values
            json_field: Optional field name to extract from JSON payload
                       (e.g., "pm_2_5", "temp"). If None, uses first numeric value.
        """
        if mqtt is None:
            raise RuntimeError("paho-mqtt not installed. Install via: pip install paho-mqtt")

        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.qos = qos
        self.keepalive = keepalive
        self.metric_store = metric_store
        self.json_field = json_field

        # Use VERSION1 API (warnings filtered globally above)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe

        self.running = False
        self.connected = False
        self.last_value = None
        self.last_update_time = None

        logger.info(
            f"MQTTSubscriber initialized: broker={broker_host}:{broker_port}, "
            f"topic={topic}, qos={qos}"
        )

    def _on_connect(self, client, userdata, flags, rc):
        """Called when connected to broker."""
        if rc == 0:
            logger.info(f"Connected to MQTT broker: {self.broker_host}:{self.broker_port}")
            self.connected = True

            # Subscribe to topic after successful connection
            try:
                client.subscribe(self.topic, self.qos)
                logger.info(f"Subscribed to topic: {self.topic}")
            except Exception as e:
                logger.error(f"Failed to subscribe to topic: {e}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Called when disconnected from broker."""
        self.connected = False
        if rc == 0:
            logger.info("Gracefully disconnected from MQTT broker")
        else:
            logger.warning(f"Unexpected disconnect from MQTT broker (code {rc})")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Called when subscription is acknowledged."""
        logger.debug(f"Subscription acknowledged (mid={mid}, qos={granted_qos})")

    def _on_message(self, client, userdata, msg):
        """Called when message is received on subscribed topic."""
        try:
            payload = msg.payload.decode('utf-8')
            logger.debug(f"Message received on {msg.topic}: {payload}")

            # Try to parse as JSON first
            try:
                data = json.loads(payload)

                # If json_field is specified, try to extract that field
                if self.json_field and isinstance(data, dict):
                    if self.json_field in data:
                        value = float(data[self.json_field])
                        logger.debug(f"Extracted field '{self.json_field}': {value}")
                    else:
                        available_fields = ', '.join(data.keys())
                        logger.warning(
                            f"Field '{self.json_field}' not found in JSON. "
                            f"Available fields: {available_fields}"
                        )
                        return
                elif isinstance(data, dict) and 'value' in data:
                    value = float(data['value'])
                elif isinstance(data, (int, float)):
                    value = float(data)
                else:
                    # Try to extract first numeric value from JSON
                    for v in data.values() if isinstance(data, dict) else data:
                        try:
                            value = float(v)
                            break
                        except (ValueError, TypeError):
                            continue
                    else:
                        logger.warning(f"Could not extract numeric value from JSON: {payload}")
                        return
            except json.JSONDecodeError:
                # Not JSON, try direct float conversion
                value = float(payload)

            # Update metric store if available
            if self.metric_store:
                self.metric_store.update(value)

            self.last_value = value
            self.last_update_time = time.time()

            logger.info(f"Updated metric: {value}")

        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse message payload '{payload}': {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def start(self):
        """Start the MQTT subscriber in a background thread.

        Non-blocking call that maintains connection and processes messages.
        """
        if self.running:
            logger.warning("MQTT subscriber already running")
            return

        try:
            logger.info(f"Starting MQTT subscriber (connecting to {self.broker_host}:{self.broker_port})")
            self.client.connect(self.broker_host, self.broker_port, self.keepalive)
            self.client.loop_start()  # Start background thread
            self.running = True

            # Wait a bit for initial connection
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to start MQTT subscriber: {e}")
            self.running = False
            raise

    def stop(self):
        """Stop the MQTT subscriber gracefully."""
        if not self.running:
            logger.warning("MQTT subscriber not running")
            return

        try:
            logger.info("Stopping MQTT subscriber")
            self.client.loop_stop()
            self.client.disconnect()
            self.running = False
        except Exception as e:
            logger.error(f"Error stopping MQTT subscriber: {e}")

    def get_latest_metric(self) -> Optional[float]:
        """Get the most recently received metric value.

        Returns:
            Float value or None if no message received yet
        """
        return self.last_value

    def is_connected(self) -> bool:
        """Check if currently connected to MQTT broker.

        Returns:
            True if connected, False otherwise
        """
        return self.connected

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
