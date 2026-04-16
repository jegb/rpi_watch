"""Unit tests for the Saleae SPI debug harness."""

import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "test_saleae_spi_debug.py"
SPEC = importlib.util.spec_from_file_location("saleae_spi_debug_under_test", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestSaleaeSpiDebugHelpers(unittest.TestCase):
    """Tests for hardware-independent helper functions."""

    def test_parse_probe_spec_accepts_prefixed_values(self):
        """Probe specs should support hex command bytes."""
        command, length = MODULE._parse_probe_spec("0x04:4")
        self.assertEqual(command, 0x04)
        self.assertEqual(length, 4)

    def test_parse_probe_spec_rejects_missing_length(self):
        """Probe specs without a byte count should fail fast."""
        with self.assertRaises(ValueError):
            MODULE._parse_probe_spec("0x04")

    def test_build_window_pattern_produces_rgb565_payload(self):
        """The pattern generator should emit 2 bytes per pixel."""
        payload = MODULE._build_window_pattern(4)
        self.assertEqual(len(payload), 4 * 4 * 2)
        self.assertEqual(payload[:8], bytes.fromhex("F8 00 F8 00 07 E0 07 E0"))

    def test_infer_logical_spi_cs_gpio_for_spi0(self):
        """SPI0 device numbers should map to the standard Raspberry Pi CE GPIOs."""
        self.assertEqual(MODULE._infer_logical_spi_cs_gpio(0, 0), 8)
        self.assertEqual(MODULE._infer_logical_spi_cs_gpio(0, 1), 7)
        self.assertIsNone(MODULE._infer_logical_spi_cs_gpio(1, 0))

    def test_panel_cs_description_prefers_hardware_spi_context(self):
        """The harness should describe hardware-managed CS clearly when panel CS is unset."""
        self.assertEqual(
            MODULE._panel_cs_description(None, 8),
            "hardware SPI CE on GPIO8",
        )
        self.assertEqual(
            MODULE._panel_cs_description(5, 8),
            "manual GPIO5",
        )
        self.assertEqual(
            MODULE._panel_cs_description(None, None),
            "unmanaged / tied low",
        )

    def test_saleae_analyzer_settings_include_available_channels(self):
        """Only provided channels should be included in analyzer settings."""
        settings = MODULE._saleae_analyzer_settings(
            clock_channel=0,
            mosi_channel=1,
            miso_channel=None,
            cs_channel=2,
        )
        self.assertEqual(settings["Clock"], 0)
        self.assertEqual(settings["MOSI"], 1)
        self.assertEqual(settings["Enable"], 2)
        self.assertNotIn("MISO", settings)

    def test_saleae_analyzer_settings_omit_enable_without_cs_channel(self):
        """The analyzer config should not require a CS channel."""
        settings = MODULE._saleae_analyzer_settings(
            clock_channel=0,
            mosi_channel=1,
            miso_channel=None,
            cs_channel=None,
        )
        self.assertNotIn("Enable", settings)

    def test_step_choices_include_display_control_probes(self):
        """The CLI should expose the extra display-state control steps."""
        for step in [
            "software-reset",
            "sleep-in",
            "sleep-out",
            "display-off",
            "display-on",
            "invert-off",
            "invert-on",
            "all-pixels-off",
            "all-pixels-on",
            "normal-on",
        ]:
            self.assertIn(step, MODULE.STEP_CHOICES)


if __name__ == "__main__":
    unittest.main()
