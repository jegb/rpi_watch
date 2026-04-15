#!/usr/bin/env python3
"""Test GC9A01 display initialization and rendering.

Initializes the display and shows a test pattern or metric value.
Run this after test_i2c_bus.py succeeds.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import time
import logging
import yaml

from rpi_watch.display import GC9A01_I2C, MetricRenderer
from rpi_watch.utils import setup_logging

setup_logging('INFO')
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'

    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)


def test_display_init(config):
    """Test display initialization.

    Args:
        config: Configuration dictionary
    """
    logger.info("=" * 60)
    logger.info("RPi Watch - Display Initialization Test")
    logger.info("=" * 60)

    try:
        display_config = config.get('display', {})
        i2c_address = int(display_config.get('i2c_address', '0x3C'), 0)
        i2c_bus = display_config.get('i2c_bus', 1)

        logger.info(f"\nInitializing display at 0x{i2c_address:02X} on I2C bus {i2c_bus}...")

        # Create and initialize display
        display = GC9A01_I2C(i2c_address=i2c_address, i2c_bus=i2c_bus)
        display.connect()
        display.init_display()

        logger.info("✓ Display initialized successfully!")

        # Wait a moment for display to stabilize
        time.sleep(1)

        # Initialize renderer
        metric_config = config.get('metric_display', {})
        renderer = MetricRenderer(
            font_path=metric_config.get('font_path'),
            font_size=metric_config.get('font_size', 80),
            text_color=tuple(metric_config.get('text_color', [255, 255, 255])),
            background_color=tuple(metric_config.get('background_color', [0, 0, 0]))
        )

        logger.info("✓ Renderer initialized")

        # Display test patterns
        logger.info("\nDisplaying test patterns...")

        # Test 1: Show a number
        logger.info("Test 1: Displaying number 42")
        image = renderer.render_and_mask(42.0, decimal_places=1)
        display.display(image)
        time.sleep(2)

        # Test 2: Show another number
        logger.info("Test 2: Displaying number 99.9")
        image = renderer.render_and_mask(99.9, decimal_places=1, unit_label="°C")
        display.display(image)
        time.sleep(2)

        # Test 3: Show zero
        logger.info("Test 3: Displaying number 0")
        image = renderer.render_and_mask(0.0, decimal_places=0)
        display.display(image)
        time.sleep(2)

        logger.info("\n✓ Display test successful!")
        logger.info("If you see numbers on your circular display, hardware is working!")

        # Cleanup
        display.disconnect()

    except Exception as e:
        logger.error(f"\n✗ Display test failed: {e}", exc_info=True)
        logger.error("\nTroubleshooting:")
        logger.error("1. Verify I2C address in config.yaml (should match i2cdetect output)")
        logger.error("2. Check physical connection of display to I2C bus")
        logger.error("3. Verify display has adequate power supply")
        logger.error("4. Check if I2C clock speed needs adjustment")
        sys.exit(1)


def main():
    """Run display initialization test."""
    try:
        config = load_config()
        test_display_init(config)
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
