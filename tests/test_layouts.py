"""Unit tests for display layout classes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from PIL import Image

from rpi_watch.display.layouts import MetricRingLayout, PMBarsLayout


class TestDisplayLayouts(unittest.TestCase):
    """Smoke tests for newly added layout classes."""

    def test_pm_bars_layout_renders_image(self):
        layout = PMBarsLayout(width=240, height=240)
        image = layout.render(
            {
                "pm_1_0": 4.2,
                "pm_2_5": 8.1,
                "pm_4_0": 13.4,
                "pm_10_0": 18.7,
            }
        )
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (240, 240))

    def test_pm_bars_layout_supports_vertical_orientation(self):
        layout = PMBarsLayout(width=240, height=240)
        image = layout.render(
            {
                "pm_1_0": 4.2,
                "pm_2_5": 8.1,
                "pm_4_0": 13.4,
                "pm_10_0": 18.7,
            },
            orientation="vertical",
        )
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (240, 240))

    def test_metric_ring_layout_renders_image(self):
        layout = MetricRingLayout(width=240, height=240)
        image = layout.render(
            26.5,
            title="TEMP",
            unit="°C",
            min_value=0.0,
            max_value=40.0,
        )
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (240, 240))


if __name__ == '__main__':
    unittest.main()
