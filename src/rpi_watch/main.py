"""Main entry point for RPi Watch application.

Orchestrates the event loop that:
1. Receives MQTT metric updates
2. Renders metrics to PIL Images
3. Displays on I2C-connected GC9A01 display
"""

import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from .display import GC9A01_SPI, MetricRenderer
from .metrics import MetricStore
from .mqtt import MQTTSubscriber
from .utils import setup_logging

logger = logging.getLogger(__name__)

DEFAULT_FIELD_PRIORITY = (
    'pm_2_5',
    'pm_10_0',
    'pm_1_0',
    'pm_4_0',
    'temp',
    'humidity',
)

FIELD_DISPLAY_DEFAULTS = {
    'pm_1_0': {'decimal_places': 1, 'title_label': 'PM1.0', 'unit_label': 'µg/m³'},
    'pm_2_5': {'decimal_places': 1, 'title_label': 'PM2.5', 'unit_label': 'µg/m³'},
    'pm_4_0': {'decimal_places': 1, 'title_label': 'PM4.0', 'unit_label': 'µg/m³'},
    'pm_10_0': {'decimal_places': 1, 'title_label': 'PM10', 'unit_label': 'µg/m³'},
    'temp': {'decimal_places': 1, 'title_label': 'TEMP', 'unit_label': '°C'},
    'humidity': {'decimal_places': 1, 'title_label': 'HUMID', 'unit_label': '%'},
}


class RPiWatch:
    """Main application controller for RPi Watch."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the RPi Watch application.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config = self._load_config(config_path)
        self.running = False

        # Initialize logging
        setup_logging(
            level=self.config.get('logging', {}).get('level', 'INFO'),
            log_file=self.config.get('logging', {}).get('log_file')
        )

        logger.info("Initializing RPi Watch application")

        # Initialize components
        self.metric_store = MetricStore()
        self.display = None
        self.renderer = None
        self.mqtt_subscriber = None

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def initialize_components(self) -> None:
        """Initialize display, renderer, and MQTT subscriber."""
        try:
            # Initialize display
            display_config = self.config.get('display', {})
            self.display = GC9A01_SPI(
                spi_bus=display_config.get('spi_bus', 0),
                spi_device=display_config.get('spi_device', 0),
                spi_speed=display_config.get('spi_speed', 10000000),
                dc_pin=display_config.get('spi_dc_pin', 25),
                reset_pin=display_config.get('spi_reset_pin', 27),
                cs_pin=display_config.get('spi_cs_pin'),
                manual_cs=display_config.get('spi_manual_cs', True),
                madctl=display_config.get('madctl', GC9A01_SPI.DEFAULT_MADCTL),
            )
            self.display.connect()
            self.display.init_display()

            # Initialize renderer
            metric_config = self.config.get('metric_display', {})
            self.renderer = MetricRenderer(
                width=display_config.get('width', 240),
                height=display_config.get('height', 240),
                font_path=metric_config.get('font_path'),
                font_size=metric_config.get('font_size', 80),
                title_font_size=metric_config.get('title_font_size'),
                unit_font_size=metric_config.get('unit_font_size'),
                text_color=tuple(metric_config.get('text_color', [255, 255, 255])),
                background_color=tuple(metric_config.get('background_color', [0, 0, 0])),
                padding=metric_config.get('padding', 18),
                title_gap=metric_config.get('title_gap', 10),
                unit_gap=metric_config.get('unit_gap', 6),
            )

            # Initialize MQTT subscriber
            mqtt_config = self.config.get('mqtt', {})
            self.mqtt_subscriber = MQTTSubscriber(
                broker_host=mqtt_config.get('broker_host', 'localhost'),
                broker_port=mqtt_config.get('broker_port', 1883),
                topic=mqtt_config.get('topic', 'sensor/metric'),
                qos=mqtt_config.get('qos', 1),
                keepalive=mqtt_config.get('keepalive', 60),
                metric_store=self.metric_store,
                json_field=mqtt_config.get('json_field')
            )

            logger.info("All components initialized successfully")

        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            self.cleanup()
            raise

    def _get_metric_display_config(self) -> dict:
        """Return metric display configuration."""
        return self.config.get('metric_display', {})

    def _get_preferred_metric_field(self) -> Optional[str]:
        """Return the preferred payload field to display."""
        metric_config = self._get_metric_display_config()
        mqtt_config = self.config.get('mqtt', {})
        return metric_config.get('metric_key') or mqtt_config.get('json_field')

    def _get_display_metadata(self, field_name: Optional[str]) -> dict:
        """Resolve display labels for a metric field."""
        metric_config = self._get_metric_display_config()
        preferred_field = self._get_preferred_metric_field()
        field_name = field_name or preferred_field
        display_defaults = FIELD_DISPLAY_DEFAULTS.get(field_name, {})
        is_preferred_field = field_name == preferred_field

        if is_preferred_field:
            title_label = metric_config.get(
                'title_label',
                display_defaults.get('title_label', field_name or ''),
            )
            unit_label = metric_config.get(
                'unit_label',
                display_defaults.get('unit_label', ''),
            )
        else:
            title_label = display_defaults.get(
                'title_label',
                metric_config.get('title_label', field_name or ''),
            )
            unit_label = display_defaults.get(
                'unit_label',
                metric_config.get('unit_label', ''),
            )

        return {
            'field': field_name,
            'title_label': title_label,
            'unit_label': unit_label,
            'decimal_places': metric_config.get(
                'decimal_places',
                display_defaults.get('decimal_places', 1),
            ),
        }

    def _get_placeholder_metric(self) -> Optional[dict]:
        """Return placeholder display settings when no reading is available."""
        metric_config = self._get_metric_display_config()
        placeholder_text = metric_config.get('placeholder_text', '--.-')

        if metric_config.get('show_placeholder', True) is False:
            return None

        preferred_field = self._get_preferred_metric_field()
        display_metadata = self._get_display_metadata(preferred_field)
        return {
            'text': str(placeholder_text),
            'title_label': metric_config.get(
                'placeholder_title_label',
                display_metadata.get('title_label', ''),
            ),
            'unit_label': metric_config.get(
                'placeholder_unit_label',
                display_metadata.get('unit_label', ''),
            ),
        }

    def _display_metric_value(
        self,
        value: float | str,
        decimal_places: int,
        title_label: str,
        unit_label: str,
    ) -> None:
        """Render and display a metric or placeholder."""
        image = self.renderer.render_and_mask(
            value,
            decimal_places=decimal_places,
            title_label=title_label,
            unit_label=unit_label,
        )
        self.display.display(image)

    def _select_display_metric(self, payload: Optional[dict]) -> Optional[dict]:
        """Choose which field from the latest payload should be displayed."""
        if not payload:
            return None

        numeric_payload = self.metric_store.extract_numeric_payload(payload)
        if not numeric_payload:
            return None

        preferred_field = self._get_preferred_metric_field()

        field_name = None
        if preferred_field and preferred_field in numeric_payload:
            field_name = preferred_field
        else:
            for candidate in DEFAULT_FIELD_PRIORITY:
                if candidate in numeric_payload:
                    field_name = candidate
                    break

        if field_name is None:
            field_name = next(iter(numeric_payload))

        display_metadata = self._get_display_metadata(field_name)

        return {
            'field': field_name,
            'value': numeric_payload[field_name],
            'decimal_places': display_metadata['decimal_places'],
            'title_label': display_metadata['title_label'],
            'unit_label': display_metadata['unit_label'],
        }

    def run(self) -> None:
        """Run the main event loop.

        Continuously reads metrics from metric_store and updates the display.
        """
        if self.display is None or self.renderer is None or self.mqtt_subscriber is None:
            raise RuntimeError("Components not initialized. Call initialize_components() first.")

        try:
            logger.info("Starting main event loop")
            self.running = True

            # Start MQTT subscriber (optional - app works offline if broker unavailable)
            try:
                logger.info("Attempting to connect to MQTT broker...")
                self.mqtt_subscriber.start()
                logger.info("✓ MQTT subscriber started")
            except TimeoutError:
                logger.warning("⚠ MQTT broker timeout - running in offline mode")
                logger.warning("  App will display metrics if manually updated")
                logger.warning(
                    f"  To use MQTT: verify broker is running at "
                    f"{self.mqtt_subscriber.broker_host}:{self.mqtt_subscriber.broker_port}"
                )
            except Exception as e:
                logger.warning(f"⚠ Failed to connect to MQTT broker: {e}")
                logger.warning("  Running in offline mode - display ready for test data")

            # Get configuration
            display_config = self.config.get('display', {})
            metric_config = self._get_metric_display_config()
            placeholder_metric = self._get_placeholder_metric()
            refresh_rate = display_config.get('refresh_rate_hz', 2)
            frame_time = 1.0 / refresh_rate

            # Main event loop
            frame_count = 0
            last_render_state = None

            while self.running:
                try:
                    current_payload = self.metric_store.get_payload()
                    current_value = self.metric_store.get_latest()
                    selected_metric = self._select_display_metric(current_payload)

                    if selected_metric is not None:
                        render_state = (
                            'metric',
                            selected_metric['field'],
                            selected_metric['value'],
                            selected_metric['decimal_places'],
                            selected_metric['title_label'],
                            selected_metric['unit_label'],
                        )

                        # Only update display if value changed (reduces SPI traffic)
                        if render_state != last_render_state:
                            self._display_metric_value(
                                selected_metric['value'],
                                decimal_places=selected_metric['decimal_places'],
                                title_label=selected_metric['title_label'],
                                unit_label=selected_metric['unit_label'],
                            )
                            last_render_state = render_state
                            frame_count += 1
                            logger.debug(
                                f"Display updated (frame {frame_count}): "
                                f"{selected_metric['field']}={selected_metric['value']}"
                            )
                    elif current_value is not None:
                        display_metadata = self._get_display_metadata(self._get_preferred_metric_field())
                        render_state = (
                            'scalar',
                            current_value,
                            display_metadata['decimal_places'],
                            display_metadata['title_label'],
                            display_metadata['unit_label'],
                        )

                        if render_state != last_render_state:
                            self._display_metric_value(
                                current_value,
                                decimal_places=display_metadata['decimal_places'],
                                title_label=display_metadata['title_label'],
                                unit_label=display_metadata['unit_label'],
                            )
                            last_render_state = render_state
                            frame_count += 1
                            logger.debug(f"Display updated (frame {frame_count}): {current_value}")
                    elif placeholder_metric is not None:
                        render_state = (
                            'placeholder',
                            placeholder_metric['text'],
                            placeholder_metric['title_label'],
                            placeholder_metric['unit_label'],
                        )

                        if render_state != last_render_state:
                            logger.info(
                                "Displaying placeholder metric until first MQTT update: %s",
                                placeholder_metric['text'],
                            )
                            self._display_metric_value(
                                placeholder_metric['text'],
                                decimal_places=metric_config.get('decimal_places', 1),
                                title_label=placeholder_metric['title_label'],
                                unit_label=placeholder_metric['unit_label'],
                            )
                            last_render_state = render_state
                    else:
                        render_state = ('waiting',)
                        if render_state != last_render_state:
                            logger.info("Waiting for MQTT metric...")
                            self._display_waiting()
                            last_render_state = render_state

                    # Sleep for frame time
                    time.sleep(frame_time)

                except Exception as e:
                    logger.error(f"Error in event loop: {e}")
                    # Continue running despite errors
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.cleanup()

    def _display_waiting(self) -> None:
        """Display a "waiting" message on the screen."""
        try:
            placeholder_metric = self._get_placeholder_metric() or {}
            image = self.renderer.render_and_mask(
                "--.-",
                decimal_places=1,
                title_label=placeholder_metric.get('title_label', ''),
                unit_label=placeholder_metric.get(
                    'unit_label',
                    self._get_metric_display_config().get('unit_label', ''),
                ),
            )
            self.display.display(image)
        except Exception as e:
            logger.warning(f"Failed to display waiting message: {e}")

    def cleanup(self) -> None:
        """Clean up resources and shut down gracefully."""
        logger.info("Cleaning up resources...")
        self.running = False

        if self.mqtt_subscriber:
            try:
                self.mqtt_subscriber.stop()
            except Exception as e:
                logger.warning(f"Error stopping MQTT subscriber: {e}")

        if self.display:
            try:
                self.display.disconnect()
            except Exception as e:
                logger.warning(f"Error closing display: {e}")

        logger.info("Cleanup complete")

    def handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.running = False


def main():
    """Main entry point for the application."""
    try:
        # Determine config path
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

        # Create application
        app = RPiWatch(str(config_path))

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, app.handle_signal)
        signal.signal(signal.SIGTERM, app.handle_signal)

        # Initialize and run
        app.initialize_components()
        app.run()

    except Exception as e:
        logger.error(f"Application failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
