"""Unit tests for MetricRenderer."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from PIL import Image

from rpi_watch.display.renderer import MetricRenderer


class TestMetricRenderer(unittest.TestCase):
    """Tests for MetricRenderer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.renderer = MetricRenderer(width=240, height=240, font_size=80)

    def test_initialization(self):
        """Test renderer initialization."""
        self.assertEqual(self.renderer.width, 240)
        self.assertEqual(self.renderer.height, 240)
        self.assertEqual(self.renderer.font_size, 80)
        self.assertIsNotNone(self.renderer.font)
        self.assertIsNotNone(self.renderer.circular_mask)

    def test_render_metric_returns_image(self):
        """Test that render_metric returns a PIL Image."""
        image = self.renderer.render_metric(42.5)
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (240, 240))
        self.assertEqual(image.mode, 'RGB')

    def test_render_metric_formatting(self):
        """Test metric value formatting."""
        # Test with 1 decimal place (default)
        image1 = self.renderer.render_metric(23.456, decimal_places=1)
        self.assertIsInstance(image1, Image.Image)

        # Test with 0 decimal places
        image2 = self.renderer.render_metric(23.456, decimal_places=0)
        self.assertIsInstance(image2, Image.Image)

        # Test with 2 decimal places
        image3 = self.renderer.render_metric(23.456, decimal_places=2)
        self.assertIsInstance(image3, Image.Image)

    def test_render_metric_with_unit(self):
        """Test rendering metric with unit label."""
        image = self.renderer.render_metric(23.5, decimal_places=1, unit_label="°C")
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (240, 240))

    def test_apply_circular_mask(self):
        """Test circular mask application."""
        # Create a simple test image
        test_image = Image.new('RGB', (240, 240), color=(255, 255, 255))

        # Apply circular mask
        masked = self.renderer.apply_circular_mask(test_image)

        # Check result is valid image
        self.assertIsInstance(masked, Image.Image)
        self.assertEqual(masked.size, (240, 240))
        self.assertEqual(masked.mode, 'RGB')

    def test_circular_mask_corners_are_black(self):
        """Test that corners are black after circular masking."""
        # Create white test image
        test_image = Image.new('RGB', (240, 240), color=(255, 255, 255))

        # Apply mask
        masked = self.renderer.apply_circular_mask(test_image)

        # Check corners are black (background color)
        corner_pixels = [
            masked.getpixel((0, 0)),
            masked.getpixel((239, 0)),
            masked.getpixel((0, 239)),
            masked.getpixel((239, 239)),
        ]

        # All corners should be background color (0, 0, 0)
        for pixel in corner_pixels:
            self.assertEqual(pixel, (0, 0, 0), "Corner pixel should be background color")

    def test_render_and_mask(self):
        """Test combined render and mask operation."""
        image = self.renderer.render_and_mask(42.0, decimal_places=1, unit_label="W")
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.size, (240, 240))
        self.assertEqual(image.mode, 'RGB')

    def test_different_values(self):
        """Test rendering various numeric values."""
        test_values = [0, 1, 10, 99.9, 100, 1000, -5, -99.99, 3.14159]

        for value in test_values:
            with self.subTest(value=value):
                image = self.renderer.render_metric(value)
                self.assertIsInstance(image, Image.Image)
                self.assertEqual(image.size, (240, 240))

    def test_custom_colors(self):
        """Test rendering with custom colors."""
        renderer = MetricRenderer(
            width=240, height=240,
            text_color=(0, 255, 0),  # Green
            background_color=(0, 0, 255)  # Blue
        )

        image = renderer.render_metric(42.0)
        self.assertIsInstance(image, Image.Image)
        self.assertEqual(image.mode, 'RGB')

    def test_mask_is_circular(self):
        """Test that mask creates approximately circular shape."""
        # Create test image with all white
        test_image = Image.new('RGB', (240, 240), color=(255, 255, 255))

        # Apply circular mask
        masked = self.renderer.apply_circular_mask(test_image)

        # Sample pixels at various distances from center
        center = 120
        radius = 118  # Should be approximately this

        # Check that pixels near edge of circle have both white and black
        # (transition from circle to corners)
        samples_found = False
        for x in range(center - 130, center + 130):
            pixel = masked.getpixel((x, center))
            if pixel == (255, 255, 255) or pixel == (0, 0, 0):
                samples_found = True

        self.assertTrue(samples_found, "Should find both white and black pixels in image")


if __name__ == '__main__':
    unittest.main()
