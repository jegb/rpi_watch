#!/usr/bin/env python3
"""Integration tests combining all components.

Tests SPI driver + components + layouts in realistic scenarios.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import time
import yaml

from rpi_watch.display.gc9a01_spi import GC9A01_SPI
from rpi_watch.display.components import TextRenderer, CircularGauge, ProgressBar, TextSize
from rpi_watch.display.layouts import (
    LargeMetricLayout,
    MetricWithGaugeLayout,
    MultiRingGaugeLayout,
    SplitMetricsLayout,
    RadialDashboardLayout,
    ColorScheme,
)
from rpi_watch.display.renderer import MetricRenderer
from rpi_watch.metrics import MetricStore
from rpi_watch.mqtt.subscriber import MQTTSubscriber
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


class IntegrationTestSuite:
    """Integration tests for complete system."""

    def __init__(self):
        """Initialize integration test suite."""
        self.display = None
        self.metric_store = MetricStore()
        self.results = []
        self.font_path = load_metric_font_path()

    def setup_display(self) -> bool:
        """Set up display for testing."""
        try:
            logger.info("Setting up display...")
            self.display = GC9A01_SPI(
                spi_bus=0,
                spi_device=0,
                spi_speed=10000000,
                dc_pin=24,
                reset_pin=25,
                cs_pin=8,
            )
            self.display.connect()
            self.display.init_display()
            logger.info("✓ Display setup complete")
            return True
        except Exception as e:
            logger.error(f"✗ Display setup failed: {e}")
            return False

    def test_text_rendering_suite(self) -> bool:
        """Test 1: Text rendering at different sizes."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 1: Text Rendering Suite")
        logger.info("─" * 70)

        try:
            text_renderer = TextRenderer(font_path=self.font_path)

            # Test all text sizes
            sizes = [TextSize.XL, TextSize.LARGE, TextSize.NORMAL, TextSize.SMALL, TextSize.TINY]

            for size in sizes:
                logger.info(f"  Testing text size: {size.name}")
                img = text_renderer.render_text(
                    f"TEST {size.value}pt",
                    size=size,
                    color=(0, 255, 0),
                )
                if not self.display:
                    continue
                # In real test: self.display.display(img)
                time.sleep(0.1)

            logger.info("✓ Text rendering suite passed")
            return True

        except Exception as e:
            logger.error(f"✗ Text rendering test failed: {e}")
            return False

    def test_gauge_animation(self) -> bool:
        """Test 2: Gauge animation (0-100%)."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 2: Gauge Animation")
        logger.info("─" * 70)

        try:
            gauge = CircularGauge(font_path=self.font_path)
            logger.info("  Animating gauge from 0% to 100%")

            # Animate gauge from 0 to 100
            steps = 10
            for i in range(steps + 1):
                value = (i / steps) * 100
                logger.info(f"    Step {i}/{steps}: {value:.0f}%")

                img = gauge.render_gauge(
                    value=value,
                    min_value=0.0,
                    max_value=100.0,
                    gauge_color=(0, 255, 0),
                    show_value=True,
                )

                if self.display:
                    # Uncomment for hardware testing:
                    # self.display.display(img)
                    pass

                time.sleep(0.05)  # Small delay between frames

            logger.info("✓ Gauge animation test passed")
            return True

        except Exception as e:
            logger.error(f"✗ Gauge animation test failed: {e}")
            return False

    def test_progress_sequence(self) -> bool:
        """Test 3: Progress indicators sequence."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 3: Progress Indicators")
        logger.info("─" * 70)

        try:
            progress = ProgressBar(font_path=self.font_path)
            logger.info("  Testing linear and circular progress")

            progress_values = [0, 25, 50, 75, 100]

            for pct in progress_values:
                logger.info(f"    Progress: {pct}%")

                # Linear
                img_linear = progress.render_linear_progress(
                    progress=pct,
                    max_progress=100,
                    bar_color=(0, 200, 100),
                )

                # Circular
                img_circular = progress.render_circular_progress(
                    progress=pct,
                    max_progress=100,
                    progress_color=(100, 200, 255),
                )

                if self.display:
                    # Alternate between linear and circular
                    # self.display.display(img_linear if pct % 2 == 0 else img_circular)
                    pass

                time.sleep(0.1)

            logger.info("✓ Progress indicators test passed")
            return True

        except Exception as e:
            logger.error(f"✗ Progress indicators test failed: {e}")
            return False

    def test_layout_sequence(self) -> bool:
        """Test 4: Display different layout types."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 4: Layout Sequence")
        logger.info("─" * 70)

        try:
            layouts_to_test = [
                ("Large Metric", LargeMetricLayout),
                ("Metric + Gauge", MetricWithGaugeLayout),
                ("Split Metrics", SplitMetricsLayout),
                ("Radial Dashboard", RadialDashboardLayout),
            ]

            for layout_name, LayoutClass in layouts_to_test:
                logger.info(f"  Testing: {layout_name}")
                layout = LayoutClass(color_scheme=ColorScheme.BRIGHT, font_path=self.font_path)

                # Render based on layout type
                if layout_name == "Large Metric":
                    img = layout.render(
                        value=42.0,
                        title="Test Value",
                        detail="Integration Test",
                        unit="",
                    )
                elif layout_name == "Metric + Gauge":
                    img = layout.render(
                        value=50.0,
                        min_value=0,
                        max_value=100,
                        title="Test Metric",
                        unit="%",
                    )
                elif layout_name == "Split Metrics":
                    img = layout.render(
                        left_value=23.5,
                        right_value=45.0,
                        left_label="Left",
                        right_label="Right",
                    )
                elif layout_name == "Radial Dashboard":
                    img = layout.render(
                        top_value=10,
                        bottom_left_value=20,
                        bottom_right_value=30,
                    )

                if self.display:
                    # Uncomment for hardware testing:
                    # self.display.display(img)
                    pass

                time.sleep(0.2)

            logger.info("✓ Layout sequence test passed")
            return True

        except Exception as e:
            logger.error(f"✗ Layout sequence test failed: {e}")
            return False

    def test_metric_store_integration(self) -> bool:
        """Test 5: Metric store with updates."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 5: Metric Store Integration")
        logger.info("─" * 70)

        try:
            logger.info("  Testing metric updates")
            renderer = MetricRenderer(font_path=self.font_path)

            # Simulate metric updates
            test_values = [10.0, 20.5, 30.0, 25.5, 15.0]

            for value in test_values:
                logger.info(f"    Metric: {value}")
                self.metric_store.update(value)

                # Verify retrieval
                retrieved = self.metric_store.get_latest()
                assert (
                    retrieved == value
                ), f"Metric mismatch: expected {value}, got {retrieved}"

                # Render image
                img = renderer.render_metric(value, decimal_places=1, unit_label="")

                if self.display:
                    # Uncomment for hardware testing:
                    # self.display.display(img)
                    pass

                time.sleep(0.1)

            logger.info("✓ Metric store integration test passed")
            return True

        except Exception as e:
            logger.error(f"✗ Metric store integration test failed: {e}")
            return False

    def test_color_scheme_variations(self) -> bool:
        """Test 6: All color schemes."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 6: Color Scheme Variations")
        logger.info("─" * 70)

        try:
            color_schemes = [
                ColorScheme.BRIGHT,
                ColorScheme.OCEAN,
                ColorScheme.FOREST,
                ColorScheme.SUNSET,
                ColorScheme.MONOCHROME,
            ]

            for scheme in color_schemes:
                logger.info(f"  Testing: {scheme.name}")
                layout = LargeMetricLayout(color_scheme=scheme, font_path=self.font_path)

                img = layout.render(
                    value=42.0,
                    title=f"{scheme.name} Theme",
                    detail="Color Scheme Test",
                )

                if self.display:
                    # Uncomment for hardware testing:
                    # self.display.display(img)
                    pass

                time.sleep(0.1)

            logger.info("✓ Color scheme variations test passed")
            return True

        except Exception as e:
            logger.error(f"✗ Color scheme variations test failed: {e}")
            return False

    def test_sps_monitor_simulation(self) -> bool:
        """Test 7: Simulate SPS Monitor data visualization."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 7: SPS Monitor Data Simulation")
        logger.info("─" * 70)

        try:
            # Simulate SPS Monitor data sequence
            sps_sequences = [
                {
                    "name": "Good Air Quality",
                    "pm_1_0": 5.2,
                    "pm_2_5": 8.5,
                    "pm_10_0": 12.3,
                    "temp": 22.0,
                    "humidity": 45.0,
                },
                {
                    "name": "Moderate Air Quality",
                    "pm_1_0": 15.2,
                    "pm_2_5": 25.5,
                    "pm_10_0": 35.8,
                    "temp": 23.5,
                    "humidity": 50.0,
                },
                {
                    "name": "Poor Air Quality",
                    "pm_1_0": 35.2,
                    "pm_2_5": 75.5,
                    "pm_10_0": 125.8,
                    "temp": 25.0,
                    "humidity": 55.0,
                },
            ]

            for seq in sps_sequences:
                logger.info(f"  Simulating: {seq['name']}")

                # PM2.5 metric with gauge
                layout = MetricWithGaugeLayout(color_scheme=ColorScheme.SUNSET, font_path=self.font_path)
                img = layout.render(
                    value=seq["pm_2_5"],
                    min_value=0,
                    max_value=100,
                    title=f"PM2.5 ({seq['name']})",
                    unit=" µg/m³",
                )

                if self.display:
                    # Uncomment for hardware testing:
                    # self.display.display(img)
                    pass

                time.sleep(0.2)

            logger.info("✓ SPS Monitor simulation test passed")
            return True

        except Exception as e:
            logger.error(f"✗ SPS Monitor simulation test failed: {e}")
            return False

    def test_full_refresh_cycle(self) -> bool:
        """Test 8: Full display refresh cycle."""
        logger.info("\n" + "─" * 70)
        logger.info("Integration Test 8: Full Refresh Cycle")
        logger.info("─" * 70)

        try:
            if not self.display:
                logger.warning("  Display not available, skipping hardware test")
                return True

            logger.info("  Testing full display refresh cycle")

            # Create test image
            renderer = MetricRenderer(font_path=self.font_path)
            img = renderer.render_metric(99.9, decimal_places=1, unit_label="")

            # Measure refresh time
            start = time.time()
            self.display.display(img)
            elapsed = time.time() - start

            fps = 1.0 / elapsed if elapsed > 0 else 0
            logger.info(f"    Refresh time: {elapsed*1000:.1f}ms ({fps:.1f} FPS)")

            if elapsed < 0.5:  # Should refresh in under 500ms
                logger.info("✓ Full refresh cycle test passed")
                return True
            else:
                logger.warning("✗ Refresh cycle slower than expected")
                return False

        except Exception as e:
            logger.error(f"✗ Full refresh cycle test failed: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all integration tests."""
        logger.info("=" * 70)
        logger.info("RPi Watch - Integration Test Suite")
        logger.info("=" * 70)

        # Setup
        display_available = self.setup_display()

        # Tests
        tests = [
            ("Text Rendering Suite", self.test_text_rendering_suite),
            ("Gauge Animation", self.test_gauge_animation),
            ("Progress Indicators", self.test_progress_sequence),
            ("Layout Sequence", self.test_layout_sequence),
            ("Metric Store Integration", self.test_metric_store_integration),
            ("Color Scheme Variations", self.test_color_scheme_variations),
            ("SPS Monitor Simulation", self.test_sps_monitor_simulation),
            ("Full Refresh Cycle", self.test_full_refresh_cycle),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed += 1
                    self.results.append((test_name, True))
                else:
                    failed += 1
                    self.results.append((test_name, False))
            except Exception as e:
                logger.error(f"✗ {test_name}: {e}")
                failed += 1
                self.results.append((test_name, False))

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Display Available: {'Yes' if display_available else 'No (software tests only)'}")
        logger.info(f"Passed: {passed}/{len(tests)}")
        logger.info(f"Failed: {failed}/{len(tests)}")

        for test_name, result in self.results:
            status = "✅" if result else "❌"
            logger.info(f"  {status} {test_name}")

        logger.info("=" * 70)

        # Cleanup
        if self.display:
            try:
                self.display.disconnect()
            except:
                pass

        return failed == 0


def main():
    """Run integration tests."""
    try:
        suite = IntegrationTestSuite()
        success = suite.run_all_tests()
        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
