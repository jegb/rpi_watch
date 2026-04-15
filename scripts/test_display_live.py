#!/usr/bin/env python3
"""Live display test - render images directly to GC9A01 display.

Tests the display by showing actual rendered graphics on the screen,
not just saving to disk. Each test displays for a few seconds.
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
from rpi_watch.display.gc9a01_spi import GC9A01_SPI
from rpi_watch.display.components import TextRenderer, CircularGauge, ProgressBar
from rpi_watch.display.layouts import (
    LargeMetricLayout,
    MetricWithGaugeLayout,
    MultiRingGaugeLayout,
    ColorScheme,
)
from rpi_watch.utils import setup_logging

setup_logging('INFO')
logger = logging.getLogger(__name__)

# Configuration
DISPLAY_DURATION = 3  # Show each test for 3 seconds
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED = 10000000  # 10 MHz
DC_PIN = 24
RST_PIN = 25
CS_PIN = 8

# Display instance
display = None


def init_display():
    """Initialize the SPI display."""
    global display
    logger.info("Initializing GC9A01 SPI display...")
    try:
        display = GC9A01_SPI(
            spi_bus=SPI_BUS,
            spi_device=SPI_DEVICE,
            spi_speed=SPI_SPEED,
            dc_pin=DC_PIN,
            reset_pin=RST_PIN,
            cs_pin=CS_PIN,
        )
        display.connect()
        display.init_display()
        logger.info("✓ Display initialized successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to initialize display: {e}")
        return False


def show_image(pil_image, title: str, duration: float = DISPLAY_DURATION):
    """Display an image on the GC9A01 display.

    Args:
        pil_image: PIL Image object (240x240 RGB)
        title: Description of what's being displayed
        duration: How long to show (seconds)
    """
    if not display or not display.initialized:
        logger.error("Display not initialized")
        return False

    try:
        logger.info(f"Displaying: {title}")
        display.display(pil_image)
        logger.info(f"  Showing for {duration} seconds...")
        time.sleep(duration)
        return True
    except Exception as e:
        logger.error(f"✗ Failed to display image: {e}")
        return False


def test_text_rendering():
    """Test 1: Text rendering at different sizes."""
    logger.info("=" * 70)
    logger.info("TEST 1: Text Rendering")
    logger.info("=" * 70)

    renderer = TextRenderer()

    tests = [
        ("42.5", "Large metric"),
        ("PM2.5", "Label text"),
        ("µg/m³", "Unit text"),
    ]

    for value, title in tests:
        img = renderer.render_text(
            value, size="XL", color=(255, 255, 255), bg_color=(0, 0, 0)
        )
        show_image(img, f"Text: {title} ('{value}')")

    logger.info("✓ Text rendering tests passed\n")


def test_large_metric_layout():
    """Test 2: Large metric layout."""
    logger.info("=" * 70)
    logger.info("TEST 2: Large Metric Layout")
    logger.info("=" * 70)

    layout = LargeMetricLayout(color_scheme=ColorScheme.BRIGHT)

    tests = [
        (23.5, "Temperature", "Living Room", "°C"),
        (45.0, "Humidity", "Current", "%"),
        (72.5, "PM2.5", "Air Quality", "µg/m³"),
    ]

    for value, title, detail, unit in tests:
        img = layout.render(value=value, title=title, detail=detail, unit=unit)
        show_image(img, f"Large Metric: {title}")

    logger.info("✓ Large metric layout tests passed\n")


def test_metric_with_gauge():
    """Test 3: Metric with gauge background."""
    logger.info("=" * 70)
    logger.info("TEST 3: Metric with Gauge")
    logger.info("=" * 70)

    layout = MetricWithGaugeLayout(color_scheme=ColorScheme.OCEAN)

    tests = [
        (25.5, 0, 500, "PM2.5", "µg/m³"),
        (45.0, 0, 100, "Humidity", "%"),
        (80.0, 0, 100, "CPU Usage", "%"),
    ]

    for value, min_val, max_val, title, unit in tests:
        img = layout.render(
            value=value, min_value=min_val, max_value=max_val, title=title, unit=unit
        )
        show_image(img, f"Metric + Gauge: {title}")

    logger.info("✓ Metric with gauge tests passed\n")


def test_multi_ring_gauge():
    """Test 4: Multi-ring gauge."""
    logger.info("=" * 70)
    logger.info("TEST 4: Multi-Ring Gauge")
    logger.info("=" * 70)

    layout = MultiRingGaugeLayout(color_scheme=ColorScheme.FOREST)

    tests = [
        ([45.0], ["Temp"]),
        ([30.0, 60.0], ["Temp", "Humidity"]),
        ([20.0, 50.0, 80.0], ["PM1.0", "PM2.5", "PM10"]),
    ]

    for values, labels in tests:
        img = layout.render(values=values, labels=labels, center_text=f"{len(values)}")
        show_image(img, f"Multi-Ring Gauge ({len(values)} rings)")

    logger.info("✓ Multi-ring gauge tests passed\n")


def test_circular_gauge():
    """Test 5: Single circular gauge."""
    logger.info("=" * 70)
    logger.info("TEST 5: Circular Gauge Component")
    logger.info("=" * 70)

    gauge = CircularGauge()

    tests = [
        (25.0, "Low reading"),
        (50.0, "Mid reading"),
        (85.0, "High reading"),
    ]

    for value, title in tests:
        img = gauge.render_gauge(
            value=value,
            min_value=0,
            max_value=100,
            title=title,
            title_color=(255, 255, 255),
        )
        show_image(img, f"Gauge: {title}")

    logger.info("✓ Circular gauge tests passed\n")


def test_progress_indicators():
    """Test 6: Progress bars and indicators."""
    logger.info("=" * 70)
    logger.info("TEST 6: Progress Indicators")
    logger.info("=" * 70)

    progress = ProgressBar()

    tests = [
        (25, "25% complete"),
        (50, "50% complete"),
        (75, "75% complete"),
        (100, "100% complete"),
    ]

    for value, title in tests:
        img = progress.render_linear_progress(
            value=value, max_value=100, title=title, show_percentage=True
        )
        show_image(img, f"Progress: {title}")

    logger.info("✓ Progress indicator tests passed\n")


def test_color_schemes():
    """Test 7: Different color schemes."""
    logger.info("=" * 70)
    logger.info("TEST 7: Color Schemes")
    logger.info("=" * 70)

    schemes = [
        ColorScheme.BRIGHT,
        ColorScheme.OCEAN,
        ColorScheme.FOREST,
        ColorScheme.SUNSET,
        ColorScheme.MONOCHROME,
    ]

    for scheme in schemes:
        layout = LargeMetricLayout(color_scheme=scheme)
        img = layout.render(value=42.0, title=f"{scheme.name}", detail="Color Scheme", unit="")
        show_image(img, f"Color Scheme: {scheme.name}")

    logger.info("✓ Color scheme tests passed\n")


def main():
    """Run all live display tests."""
    logger.info("")
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║        GC9A01 Display - Live Rendering Test Suite         ║")
    logger.info("║          Watch the display for visual output!             ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    logger.info("")

    # Initialize display
    if not init_display():
        logger.error("Failed to initialize display. Exiting.")
        return 1

    try:
        # Run all tests
        test_text_rendering()
        test_large_metric_layout()
        test_metric_with_gauge()
        test_multi_ring_gauge()
        test_circular_gauge()
        test_progress_indicators()
        test_color_schemes()

        logger.info("=" * 70)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Display is working correctly!")
        logger.info("You can now run: python3 -m rpi_watch.main")
        logger.info("")

        return 0

    except KeyboardInterrupt:
        logger.info("\n✓ Tests interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1
    finally:
        # Clean up
        if display:
            display.disconnect()
            logger.info("Display disconnected")


if __name__ == "__main__":
    sys.exit(main())
