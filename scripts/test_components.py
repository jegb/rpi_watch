#!/usr/bin/env python3
"""Test and demonstrate display components.

Tests text rendering, gauges, and progress indicators.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import yaml
from PIL import Image, ImageDraw

from rpi_watch.display.renderer import MetricRenderer
from rpi_watch.display.components import (
    TextSize,
    TextAlignment,
    TextRenderer,
    SparklineRenderer,
    CircularGauge,
    ProgressBar,
)
from rpi_watch.display.layouts import MetricRingLayout, PMBarsLayout
from rpi_watch.metrics import serialize_guidance_bands
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


def save_test_image(image: Image.Image, filename: str):
    """Save test image to file."""
    image.save(filename)
    logger.info(f"✓ Saved: {filename}")


def test_metric_renderer():
    """Test the main metric renderer and log the resolved font."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 0: Metric Renderer Font Diagnostics")
    logger.info("=" * 70)

    font_path = load_metric_font_path()
    renderer = MetricRenderer(
        width=240,
        height=240,
        font_path=font_path,
        font_size=116,
        unit_font_size=30,
    )
    logger.info(
        "MetricRenderer font: resolved=%s scalable=%s",
        renderer.resolved_font_source,
        renderer.using_scalable_font,
    )

    samples = [
        (10.5, 1, "PM2.5", "µg/m³", "/tmp/test_metric_pm25.png"),
        (27.1, 1, "TEMP", "°C", "/tmp/test_metric_temp.png"),
        (47.8, 1, "HUMID", "%", "/tmp/test_metric_humidity.png"),
    ]

    for value, decimal_places, title_label, unit_label, filename in samples:
        image = renderer.render_and_mask(
            value=value,
            decimal_places=decimal_places,
            title_label=title_label,
            unit_label=unit_label,
        )
        save_test_image(image, filename)

    logger.info("✓ Metric renderer font diagnostics passed")


def test_text_rendering():
    """Test text rendering with different sizes."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Text Rendering")
    logger.info("=" * 70)

    renderer = TextRenderer(width=240, height=240, font_path=load_metric_font_path())
    logger.info("TextRenderer font: resolved=%s", renderer.resolved_font_source)

    # Test different sizes
    sizes = [TextSize.XL, TextSize.LARGE, TextSize.NORMAL, TextSize.SMALL, TextSize.TINY]

    for size in sizes:
        img = renderer.render_text(
            f"{size.name}: {size.value}pt",
            size=size,
            color=(0, 255, 0),
            background=(0, 0, 0),
        )
        filename = f"/tmp/test_text_{size.name.lower()}.png"
        save_test_image(img, filename)

    logger.info("✓ Text rendering tests passed")


def test_multiline_text():
    """Test multi-level text rendering."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Multi-line Text Rendering")
    logger.info("=" * 70)

    renderer = TextRenderer(width=240, height=240, font_path=load_metric_font_path())

    # Test multiline with all levels
    img = renderer.render_multiline(
        main_text="23.5",
        sub_text="Temperature",
        detail_text="Living Room",
        main_color=(255, 100, 0),  # Orange
        sub_color=(200, 200, 200),
        detail_color=(100, 100, 100),
    )
    save_test_image(img, "/tmp/test_multiline_full.png")

    # Test with only main and sub
    img = renderer.render_multiline(
        main_text="45",
        sub_text="Humidity %",
        detail_text=None,
        main_color=(0, 255, 255),  # Cyan
    )
    save_test_image(img, "/tmp/test_multiline_main_sub.png")

    logger.info("✓ Multi-line text tests passed")


def test_circular_gauge():
    """Test circular gauge rendering."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Circular Gauge Rendering")
    logger.info("=" * 70)

    gauge = CircularGauge(
        width=240,
        height=240,
        outer_radius=100,
        font_path=load_metric_font_path(),
    )

    # Test different values
    test_values = [0.0, 25.0, 50.0, 75.0, 100.0]

    for value in test_values:
        img = gauge.render_gauge(
            value=value,
            min_value=0.0,
            max_value=100.0,
            gauge_color=(0, 255, 0),
            show_value=True,
        )
        filename = f"/tmp/test_gauge_{int(value):03d}.png"
        save_test_image(img, filename)

    logger.info("✓ Circular gauge tests passed")


def test_multi_ring_gauge():
    """Test multi-ring gauge rendering."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Multi-Ring Gauge")
    logger.info("=" * 70)

    gauge = CircularGauge(
        width=240,
        height=240,
        outer_radius=110,
        font_path=load_metric_font_path(),
    )

    # Test with different number of rings
    test_cases = [
        ([50.0], "single_ring"),
        ([33.0, 66.0], "two_rings"),
        ([25.0, 50.0, 75.0], "three_rings"),
        ([20.0, 40.0, 60.0, 80.0], "four_rings"),
    ]

    for values, name in test_cases:
        img = gauge.render_multi_ring_gauge(
            values=values,
            min_value=0.0,
            max_value=100.0,
        )
        filename = f"/tmp/test_gauge_{name}.png"
        save_test_image(img, filename)

    logger.info("✓ Multi-ring gauge tests passed")


def test_linear_progress():
    """Test linear progress bar."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Linear Progress Bar")
    logger.info("=" * 70)

    progress = ProgressBar(width=240, height=240, font_path=load_metric_font_path())

    # Test different progress levels
    progress_values = [0, 25, 50, 75, 100]

    for pct in progress_values:
        img = progress.render_linear_progress(
            progress=pct,
            max_progress=100,
            bar_color=(0, 200, 100),
            show_percentage=True,
        )
        filename = f"/tmp/test_progress_linear_{pct:03d}.png"
        save_test_image(img, filename)

    logger.info("✓ Linear progress bar tests passed")


def test_circular_progress():
    """Test circular progress indicator."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 6: Circular Progress Indicator")
    logger.info("=" * 70)

    progress = ProgressBar(width=240, height=240, font_path=load_metric_font_path())

    # Test different progress levels
    progress_values = [0, 25, 50, 75, 100]

    for pct in progress_values:
        img = progress.render_circular_progress(
            progress=pct,
            max_progress=100,
            radius=80,
            ring_width=8,
            progress_color=(100, 200, 255),
        )
        filename = f"/tmp/test_progress_circular_{pct:03d}.png"
        save_test_image(img, filename)

    logger.info("✓ Circular progress indicator tests passed")


def test_sparkline_rendering():
    """Test sparkline rendering from trailing values."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 7: Sparkline Rendering")
    logger.info("=" * 70)

    sparkline = SparklineRenderer(width=240, height=48, padding=6)
    img = sparkline.render(
        [8.2, 9.1, 7.8, 10.4, 11.0, 10.1, 9.7, 8.9, 7.6, 8.4],
        background_color=(0, 0, 0),
        line_color=(92, 172, 255),
        fill_color=(18, 40, 74),
    )
    save_test_image(img, "/tmp/test_sparkline_pm25.png")

    logger.info("✓ Sparkline rendering tests passed")


def test_gradient_ring_rendering():
    """Test configurable threshold-gradient ring rendering."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 8: Gradient Ring Rendering")
    logger.info("=" * 70)

    gauge = CircularGauge(
        width=240,
        height=240,
        outer_radius=108,
        font_path=load_metric_font_path(),
    )
    img = gauge.render_gradient_ring(
        26.5,
        min_value=0.0,
        max_value=40.0,
        start_angle=135.0,
        end_angle=405.0,
        thickness=16,
        track_color=(40, 40, 40),
        thresholds=[
            {"value": 0.0, "color": [64, 128, 255]},
            {"value": 22.0, "color": [0, 220, 120]},
            {"value": 35.0, "color": [255, 96, 64]},
        ],
    )
    save_test_image(img, "/tmp/test_gradient_ring_temp.png")

    logger.info("✓ Gradient ring rendering tests passed")


def test_layout_extensions():
    """Test PM bars and metric ring layouts."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 9: Extended Layouts")
    logger.info("=" * 70)

    pm_layout = PMBarsLayout(font_path=load_metric_font_path())
    pm_img = pm_layout.render(
        {
            "pm_1_0": 3.7,
            "pm_2_5": 9.4,
            "pm_4_0": 14.8,
            "pm_10_0": 18.1,
        }
    )
    save_test_image(pm_img, "/tmp/test_layout_pm_bars.png")

    pm_vertical_img = pm_layout.render(
        {
            "pm_1_0": 3.7,
            "pm_2_5": 9.4,
            "pm_4_0": 14.8,
            "pm_10_0": 18.1,
        },
        orientation="vertical",
    )
    save_test_image(pm_vertical_img, "/tmp/test_layout_pm_bars_vertical.png")

    ring_layout = MetricRingLayout(font_path=load_metric_font_path())
    ring_img = ring_layout.render(
        27.3,
        title="TEMP",
        unit="°C",
        min_value=0.0,
        max_value=40.0,
        thresholds=[
            {"value": 0.0, "color": [64, 128, 255]},
            {"value": 22.0, "color": [0, 220, 120]},
            {"value": 35.0, "color": [255, 96, 64]},
        ],
    )
    save_test_image(ring_img, "/tmp/test_layout_metric_ring.png")

    pm_ring_img = ring_layout.render(
        42.8,
        title="PM2.5",
        unit="µg/m³",
        min_value=0.0,
        max_value=325.4,
        threshold_bands=serialize_guidance_bands("pm_2_5"),
        value_color=(251, 146, 60),
    )
    save_test_image(pm_ring_img, "/tmp/test_layout_pm25_guidance_ring.png")

    logger.info("✓ Extended layout tests passed")


def test_combined_layouts():
    """Test combined component layouts."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 10: Combined Component Layouts")
    logger.info("=" * 70)

    # Layout 1: Main metric with gauge
    logger.info("Creating layout: Main metric + gauge...")
    text_renderer = TextRenderer(font_path=load_metric_font_path())
    gauge = CircularGauge(outer_radius=90, font_path=load_metric_font_path())

    # Create base image with metric
    text_img = text_renderer.render_multiline(
        main_text="72.5",
        sub_text="Air Quality",
        detail_text="PM2.5",
        main_color=(255, 150, 0),
    )

    # Create gauge image
    gauge_img = gauge.render_gauge(
        value=72.5,
        min_value=0.0,
        max_value=500.0,
        gauge_color=(255, 150, 0),
    )

    # Blend them (overlay)
    combined = Image.blend(text_img, gauge_img, 0.3)
    save_test_image(combined, "/tmp/test_combined_metric_gauge.png")

    logger.info("✓ Combined layouts tests passed")


def test_color_variations():
    """Test different color schemes."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 11: Color Variations")
    logger.info("=" * 70)

    renderer = TextRenderer(font_path=load_metric_font_path())

    color_schemes = [
        ("Green", (0, 255, 0)),
        ("Red", (255, 0, 0)),
        ("Blue", (0, 0, 255)),
        ("Yellow", (255, 255, 0)),
        ("Cyan", (0, 255, 255)),
        ("Magenta", (255, 0, 255)),
        ("Orange", (255, 165, 0)),
    ]

    for name, color in color_schemes:
        img = renderer.render_text(
            f"{name}\n{color}",
            size=TextSize.LARGE,
            color=color,
            background=(20, 20, 20),
        )
        filename = f"/tmp/test_color_{name.lower()}.png"
        save_test_image(img, filename)

    logger.info("✓ Color variation tests passed")


def main():
    """Run all component tests."""
    try:
        logger.info("=" * 70)
        logger.info("GC9A01 Display - Component Testing Suite")
        logger.info("=" * 70)

        test_metric_renderer()
        test_text_rendering()
        test_multiline_text()
        test_circular_gauge()
        test_multi_ring_gauge()
        test_linear_progress()
        test_circular_progress()
        test_sparkline_rendering()
        test_gradient_ring_rendering()
        test_layout_extensions()
        test_combined_layouts()
        test_color_variations()

        logger.info("\n" + "=" * 70)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 70)
        logger.info("\nTest images saved to /tmp/test_*.png")
        logger.info("View with: open /tmp/test_*.png (macOS) or display /tmp/test_*.png (Linux)")

        return 0

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
