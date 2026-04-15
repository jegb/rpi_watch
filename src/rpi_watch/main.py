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
                dc_pin=display_config.get('spi_dc_pin', 24),
                reset_pin=display_config.get('spi_reset_pin', 25),
                cs_pin=display_config.get('spi_cs_pin', 8),
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
                text_color=tuple(metric_config.get('text_color', [255, 255, 255])),
                background_color=tuple(metric_config.get('background_color', [0, 0, 0]))
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

    def run(self) -> None:
        """Run the main event loop.

        Continuously reads metrics from metric_store and updates the display.
        """
        if self.display is None or self.renderer is None or self.mqtt_subscriber is None:
            raise RuntimeError("Components not initialized. Call initialize_components() first.")

        try:
            logger.info("Starting main event loop")
            self.running = True

            # Start MQTT subscriber
            self.mqtt_subscriber.start()

            # Get configuration
            display_config = self.config.get('display', {})
            metric_config = self.config.get('metric_display', {})
            refresh_rate = display_config.get('refresh_rate_hz', 2)
            frame_time = 1.0 / refresh_rate

            # Initial display showing waiting state
            self._display_waiting()
            time.sleep(2)

            # Main event loop
            frame_count = 0
            last_value = None

            while self.running:
                try:
                    # Get current metric value
                    current_value = self.metric_store.get_latest()

                    if current_value is not None:
                        # Only update display if value changed (reduces I2C traffic)
                        if current_value != last_value:
                            # Render and display metric
                            image = self.renderer.render_and_mask(
                                current_value,
                                decimal_places=metric_config.get('decimal_places', 1),
                                unit_label=metric_config.get('unit_label', '')
                            )
                            self.display.display(image)

                            last_value = current_value
                            frame_count += 1
                            logger.debug(f"Display updated (frame {frame_count}): {current_value}")
                    else:
                        # No metric received yet
                        if frame_count == 0:
                            logger.info("Waiting for MQTT metric...")
                            self._display_waiting()

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
            image = self.renderer.render_and_mask(
                0,
                decimal_places=0,
                unit_label="..."
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
