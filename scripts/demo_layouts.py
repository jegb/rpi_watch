#!/usr/bin/env python3
"""Demo application showcasing all available layouts and components.

Generates sample displays for each layout type with various data.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import time
import yaml

from rpi_watch.display.layouts import (
    LayoutType,
    ColorScheme,
    get_layout,
    LargeMetricLayout,
    MetricWithGaugeLayout,
    MultiRingGaugeLayout,
    TextOverGaugeLayout,
    SplitMetricsLayout,
    RadialDashboardLayout,
    ProgressStackLayout,
)
from rpi_watch.display.components import TextSize
from rpi_watch.utils import setup_logging

setup_logging('INFO')
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def load_metric_font_path() -> str | None:
    """Load the configured metric font path from config.yaml."""
    try:
        with open(CONFIG_PATH, "r") as handle:
            config = yaml.safe_load(handle) or {}
    except Exception as exc:
        logger.warning("Failed to load config for font path: %s", exc)
        return None

    return config.get("metric_display", {}).get("font_path")


def demo_large_metric():
    """Demo: Large metric with title and detail."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 1: Large Metric Layout")
    logger.info("=" * 70)

    layout = LargeMetricLayout(color_scheme=ColorScheme.BRIGHT, font_path=load_metric_font_path())

    # Test cases
    test_cases = [
        {"value": 23.5, "title": "Temperature", "detail": "Living Room", "unit": "°C"},
        {"value": 45.0, "title": "Humidity", "detail": "Current", "unit": "%"},
        {"value": 1025.3, "title": "Pressure", "detail": "Sea Level", "unit": " hPa"},
    ]

    for i, test in enumerate(test_cases):
        img = layout.render(**test)
        filename = f"/tmp/demo_large_metric_{i+1}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_metric_with_gauge():
    """Demo: Metric with gauge background."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 2: Metric with Gauge Layout")
    logger.info("=" * 70)

    layout = MetricWithGaugeLayout(color_scheme=ColorScheme.OCEAN, font_path=load_metric_font_path())

    # Test cases
    test_cases = [
        {
            "value": 72.5,
            "min_value": 0,
            "max_value": 500,
            "title": "PM2.5 Level",
            "unit": " µg/m³",
        },
        {
            "value": 45.0,
            "min_value": 0,
            "max_value": 100,
            "title": "Air Quality",
            "unit": "%",
        },
        {
            "value": 85.0,
            "min_value": 0,
            "max_value": 100,
            "title": "CPU Usage",
            "unit": "%",
        },
    ]

    for i, test in enumerate(test_cases):
        img = layout.render(**test)
        filename = f"/tmp/demo_metric_gauge_{i+1}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_multi_ring_gauge():
    """Demo: Multi-ring gauge for multiple metrics."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 3: Multi-Ring Gauge Layout")
    logger.info("=" * 70)

    layout = MultiRingGaugeLayout(color_scheme=ColorScheme.FOREST, font_path=load_metric_font_path())

    # Test cases with different numbers of rings
    test_cases = [
        {
            "values": [65.0],
            "labels": ["Speed"],
            "center_text": "1",
        },
        {
            "values": [45.0, 75.0],
            "labels": ["Temp", "Humidity"],
            "center_text": "2",
        },
        {
            "values": [30.0, 60.0, 90.0],
            "labels": ["R", "G", "B"],
            "center_text": "3",
        },
        {
            "values": [20.0, 40.0, 60.0, 80.0],
            "labels": ["M1", "M2", "M3", "M4"],
            "center_text": "4",
        },
    ]

    for i, test in enumerate(test_cases):
        img = layout.render(**test)
        filename = f"/tmp/demo_multi_ring_{i+1}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_text_over_gauge():
    """Demo: Large text over gauge background."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 4: Text Over Gauge Layout")
    logger.info("=" * 70)

    layout = TextOverGaugeLayout(color_scheme=ColorScheme.SUNSET, font_path=load_metric_font_path())

    # Test cases
    test_cases = [
        {"main_text": "READY", "gauge_value": 80, "sub_text": "System Status", "text_size": TextSize.LARGE},
        {"main_text": "ALERT", "gauge_value": 40, "sub_text": "Warning", "text_size": TextSize.XL},
        {"main_text": "OK", "gauge_value": 100, "sub_text": "All Good", "text_size": TextSize.LARGE},
    ]

    for i, test in enumerate(test_cases):
        img = layout.render(**test)
        filename = f"/tmp/demo_text_gauge_{i+1}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_split_metrics():
    """Demo: Two metrics side-by-side."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 5: Split Metrics Layout")
    logger.info("=" * 70)

    layout = SplitMetricsLayout(color_scheme=ColorScheme.BRIGHT, font_path=load_metric_font_path())

    # Test cases
    test_cases = [
        {
            "left_value": 23.5,
            "right_value": 45.0,
            "left_label": "Temp",
            "right_label": "Humidity",
            "left_unit": "°C",
            "right_unit": "%",
        },
        {
            "left_value": 72.5,
            "right_value": 1025.3,
            "left_label": "PM2.5",
            "right_label": "Pressure",
            "left_unit": " µg",
            "right_unit": " hPa",
        },
        {
            "left_value": 85.0,
            "right_value": 2500.0,
            "left_label": "CPU %",
            "right_label": "Memory KB",
            "left_unit": "",
            "right_unit": "",
        },
    ]

    for i, test in enumerate(test_cases):
        img = layout.render(**test)
        filename = f"/tmp/demo_split_metrics_{i+1}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_radial_dashboard():
    """Demo: Three metrics in radial arrangement."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 6: Radial Dashboard Layout")
    logger.info("=" * 70)

    layout = RadialDashboardLayout(color_scheme=ColorScheme.OCEAN, font_path=load_metric_font_path())

    # Test cases (triangular arrangement)
    test_cases = [
        {
            "top_value": 23.5,
            "bottom_left_value": 45.0,
            "bottom_right_value": 1025.3,
            "top_label": "Temp",
            "bottom_left_label": "Humid",
            "bottom_right_label": "Press",
        },
        {
            "top_value": 72.5,
            "bottom_left_value": 80.0,
            "bottom_right_value": 65.0,
            "top_label": "PM2.5",
            "bottom_left_label": "AQI",
            "bottom_right_label": "Index",
        },
        {
            "top_value": 10.0,
            "bottom_left_value": 20.0,
            "bottom_right_value": 30.0,
            "top_label": "Speed",
            "bottom_left_label": "Accel",
            "bottom_right_label": "Force",
        },
    ]

    for i, test in enumerate(test_cases):
        img = layout.render(**test)
        filename = f"/tmp/demo_radial_dashboard_{i+1}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_progress_stack():
    """Demo: Stacked progress bars."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 7: Progress Stack Layout")
    logger.info("=" * 70)

    layout = ProgressStackLayout(color_scheme=ColorScheme.FOREST, font_path=load_metric_font_path())

    # Test cases
    test_cases = [
        {
            "metrics": [
                {"value": 45, "label": "CPU", "color": (255, 0, 0)},
                {"value": 65, "label": "Memory", "color": (0, 255, 0)},
                {"value": 30, "label": "Disk", "color": (0, 0, 255)},
            ],
        },
        {
            "metrics": [
                {"value": 72.5, "label": "PM2.5", "color": (255, 100, 0)},
                {"value": 1025.3, "label": "Pressure", "color": (100, 150, 255)},
                {"value": 23.5, "label": "Temperature", "color": (255, 0, 100)},
            ],
        },
        {
            "metrics": [
                {"value": 25, "label": "Q1", "color": (100, 200, 100)},
                {"value": 50, "label": "Q2", "color": (150, 200, 100)},
                {"value": 75, "label": "Q3", "color": (200, 200, 100)},
                {"value": 90, "label": "Q4", "color": (255, 150, 0)},
            ],
        },
    ]

    for i, test in enumerate(test_cases):
        img = layout.render(**test)
        filename = f"/tmp/demo_progress_stack_{i+1}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_color_schemes():
    """Demo: Same layout with different color schemes."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 8: Color Schemes")
    logger.info("=" * 70)

    color_schemes = [
        ColorScheme.BRIGHT,
        ColorScheme.OCEAN,
        ColorScheme.FOREST,
        ColorScheme.SUNSET,
        ColorScheme.MONOCHROME,
    ]

    for scheme in color_schemes:
        layout = LargeMetricLayout(color_scheme=scheme, font_path=load_metric_font_path())
        img = layout.render(
            value=42.0,
            title=f"{scheme.name} Theme",
            detail="Color Scheme Demo",
            unit="",
        )
        filename = f"/tmp/demo_color_{scheme.name.lower()}.png"
        img.save(filename)
        logger.info(f"✓ Saved: {filename}")


def demo_sps_monitor_integration():
    """Demo: Real SPS Monitor data visualization."""
    logger.info("\n" + "=" * 70)
    logger.info("DEMO 9: SPS Monitor Integration Examples")
    logger.info("=" * 70)

    # Simulate SPS Monitor data
    sps_data = {
        "pm_1_0": 12.3,
        "pm_2_5": 25.5,
        "pm_4_0": 35.2,
        "pm_10_0": 45.8,
        "temp": 23.5,
        "humidity": 45.0,
    }

    # Layout 1: PM2.5 with gauge
    logger.info("\nLayout 1: PM2.5 with Gauge")
    layout = MetricWithGaugeLayout(color_scheme=ColorScheme.SUNSET, font_path=load_metric_font_path())
    img = layout.render(
        value=sps_data["pm_2_5"],
        min_value=0,
        max_value=500,
        title="PM2.5 Level",
        unit=" µg/m³",
    )
    img.save("/tmp/demo_sps_pm25_gauge.png")
    logger.info("✓ Saved: /tmp/demo_sps_pm25_gauge.png")

    # Layout 2: Temperature and Humidity split
    logger.info("\nLayout 2: Temperature & Humidity")
    layout = SplitMetricsLayout(color_scheme=ColorScheme.OCEAN, font_path=load_metric_font_path())
    img = layout.render(
        left_value=sps_data["temp"],
        right_value=sps_data["humidity"],
        left_label="Temperature",
        right_label="Humidity",
        left_unit="°C",
        right_unit="%",
    )
    img.save("/tmp/demo_sps_temp_humidity.png")
    logger.info("✓ Saved: /tmp/demo_sps_temp_humidity.png")

    # Layout 3: Multi-ring gauge (all PM metrics)
    logger.info("\nLayout 3: Multi-Ring PM Gauge")
    layout = MultiRingGaugeLayout(color_scheme=ColorScheme.FOREST, font_path=load_metric_font_path())
    img = layout.render(
        values=[sps_data["pm_1_0"], sps_data["pm_2_5"], sps_data["pm_10_0"]],
        labels=["PM1.0", "PM2.5", "PM10"],
        min_value=0,
        max_value=100,
        center_text="PM",
    )
    img.save("/tmp/demo_sps_multi_ring_pm.png")
    logger.info("✓ Saved: /tmp/demo_sps_multi_ring_pm.png")

    # Layout 4: Radial dashboard
    logger.info("\nLayout 4: Radial Dashboard")
    layout = RadialDashboardLayout(color_scheme=ColorScheme.BRIGHT, font_path=load_metric_font_path())
    img = layout.render(
        top_value=sps_data["temp"],
        bottom_left_value=sps_data["humidity"],
        bottom_right_value=sps_data["pm_2_5"],
        top_label="Temp",
        bottom_left_label="Humidity",
        bottom_right_label="PM2.5",
    )
    img.save("/tmp/demo_sps_radial.png")
    logger.info("✓ Saved: /tmp/demo_sps_radial.png")

    # Layout 5: Progress stack (all metrics)
    logger.info("\nLayout 5: Progress Stack")
    layout = ProgressStackLayout(color_scheme=ColorScheme.SUNSET, font_path=load_metric_font_path())
    metrics = [
        {"value": sps_data["pm_1_0"], "label": "PM1.0", "color": (255, 0, 0)},
        {"value": sps_data["pm_2_5"], "label": "PM2.5", "color": (255, 100, 0)},
        {"value": sps_data["pm_10_0"], "label": "PM10", "color": (255, 200, 0)},
    ]
    img = layout.render(metrics=metrics, max_value=100)
    img.save("/tmp/demo_sps_progress_stack.png")
    logger.info("✓ Saved: /tmp/demo_sps_progress_stack.png")


def main():
    """Run all demos."""
    try:
        logger.info("=" * 70)
        logger.info("GC9A01 Display - Layout & Component Demos")
        logger.info("=" * 70)

        demo_large_metric()
        demo_metric_with_gauge()
        demo_multi_ring_gauge()
        demo_text_over_gauge()
        demo_split_metrics()
        demo_radial_dashboard()
        demo_progress_stack()
        demo_color_schemes()
        demo_sps_monitor_integration()

        logger.info("\n" + "=" * 70)
        logger.info("ALL DEMOS COMPLETED ✓")
        logger.info("=" * 70)
        logger.info("\nGenerated demo images:")
        logger.info("  /tmp/demo_*.png")
        logger.info("\nView with:")
        logger.info("  open /tmp/demo_*.png  (macOS)")
        logger.info("  display /tmp/demo_*.png  (Linux ImageMagick)")
        logger.info("  sxiv /tmp/demo_*.png  (Linux lightweight)")

        return 0

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
