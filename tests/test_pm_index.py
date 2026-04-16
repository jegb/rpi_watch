"""Unit tests for PM guidance index helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest

from rpi_watch.metrics import (
    classify_display_band,
    classify_pm_value,
    get_guidance_display_range,
)


class TestPMIndex(unittest.TestCase):
    """Tests for ATSDR PM guidance threshold helpers."""

    def test_classify_pm25_bands(self):
        self.assertEqual(classify_pm_value("pm_2_5", 8.5).category, "Good")
        self.assertEqual(classify_pm_value("pm_2_5", 20.0).category, "Moderate")
        self.assertEqual(
            classify_pm_value("pm_2_5", 42.0).category,
            "Unhealthy for Sensitive Groups",
        )
        self.assertEqual(classify_pm_value("pm_2_5", 150.0).category, "Very Unhealthy")
        self.assertEqual(classify_pm_value("pm_2_5", 260.0).category, "Hazardous")

    def test_classify_pm10_bands(self):
        self.assertEqual(classify_pm_value("pm_10_0", 45.0).category, "Good")
        self.assertEqual(classify_pm_value("pm_10_0", 180.0).category, "Unhealthy for Sensitive Groups")
        self.assertEqual(classify_pm_value("pm_10_0", 300.0).category, "Unhealthy")
        self.assertEqual(classify_pm_value("pm_10_0", 500.0).category, "Hazardous")

    def test_display_band_for_pm1_uses_supported_pm_fields(self):
        band = classify_display_band(
            "pm_1_0",
            {
                "pm_1_0": 6.0,
                "pm_2_5": 18.0,
                "pm_10_0": 190.0,
            },
        )
        self.assertIsNotNone(band)
        self.assertEqual(band.category, "Unhealthy for Sensitive Groups")

    def test_display_band_for_pm4_uses_worst_supported_pm_band(self):
        band = classify_display_band(
            "pm_4_0",
            {
                "pm_4_0": 20.0,
                "pm_2_5": 44.0,
                "pm_10_0": 270.0,
            },
        )
        self.assertIsNotNone(band)
        self.assertEqual(band.category, "Unhealthy")

    def test_non_pm_fields_do_not_return_guidance_band(self):
        self.assertIsNone(classify_display_band("temp", {"temp": 27.1}))
        self.assertIsNone(classify_pm_value("temp", 27.1))

    def test_pm25_guidance_range_is_finite_for_ring_display(self):
        self.assertEqual(get_guidance_display_range("pm_2_5"), (0.0, 325.4))
        self.assertEqual(get_guidance_display_range("pm_10_0"), (0.0, 604.0))


if __name__ == "__main__":
    unittest.main()
