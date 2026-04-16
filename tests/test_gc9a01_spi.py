"""Unit tests for the GC9A01 SPI driver."""

import importlib.util
from pathlib import Path
from unittest import mock
import unittest

MODULE_PATH = Path(__file__).parent.parent / "src" / "rpi_watch" / "display" / "gc9a01_spi.py"
SPEC = importlib.util.spec_from_file_location("gc9a01_spi_under_test", MODULE_PATH)
gc9a01_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gc9a01_module)
GC9A01_SPI = gc9a01_module.GC9A01_SPI


class TestGC9A01SPI(unittest.TestCase):
    """Tests for GC9A01 SPI driver behavior."""

    def setUp(self):
        """Provide mock hardware modules so the driver can be instantiated."""
        self.original_spidev = gc9a01_module.spidev
        self.original_gpio = gc9a01_module.GPIO

        gc9a01_module.spidev = object()
        gc9a01_module.GPIO = mock.Mock(HIGH=1, LOW=0)

    def tearDown(self):
        """Restore module globals after each test."""
        gc9a01_module.spidev = self.original_spidev
        gc9a01_module.GPIO = self.original_gpio

    def test_reset_uses_extended_panel_timing(self):
        """Hardware reset should use the longer GC9A01 timing window."""
        driver = GC9A01_SPI()
        driver.spi = object()

        with mock.patch.object(gc9a01_module.time, "sleep") as mock_sleep:
            driver.reset()

        self.assertEqual(
            gc9a01_module.GPIO.output.call_args_list,
            [
                mock.call(driver.reset_pin, gc9a01_module.GPIO.HIGH),
                mock.call(driver.reset_pin, gc9a01_module.GPIO.LOW),
                mock.call(driver.reset_pin, gc9a01_module.GPIO.HIGH),
            ],
        )
        self.assertEqual(
            mock_sleep.call_args_list,
            [
                mock.call(driver.RESET_PULSE_HIGH_S),
                mock.call(driver.RESET_PULSE_LOW_S),
                mock.call(driver.RESET_STABILIZE_S),
            ],
        )

    def test_init_display_unlocks_registers_and_uses_configured_madctl(self):
        """Initialization should unlock extended registers and apply MADCTL."""
        driver = GC9A01_SPI(madctl="0x88")
        driver.spi = object()

        events = []

        with mock.patch.object(driver, "reset") as mock_reset, mock.patch.object(
            driver,
            "_write_command",
            side_effect=lambda command: events.append(("command", command)),
        ), mock.patch.object(
            driver,
            "_write_command_data",
            side_effect=lambda command, data: events.append(("data", command, data)),
        ), mock.patch.object(gc9a01_module.time, "sleep") as mock_sleep:
            driver.init_display()

        self.assertTrue(driver.initialized)
        mock_reset.assert_called_once_with()
        self.assertEqual(
            events[:8],
            [
                ("command", 0xFE),
                ("command", 0xEF),
                ("data", 0xB6, b"\x00\x00"),
                ("data", driver.CMD_MEMORY_ACCESS, bytes([0x88])),
                ("data", driver.CMD_INTERFACE_PIXEL_FORMAT, bytes([0x05])),
                ("data", driver.CMD_POWER_CONTROL_1, bytes([0x13])),
                ("data", driver.CMD_POWER_CONTROL_2, bytes([0x13])),
                ("data", driver.CMD_POWER_CONTROL_3, bytes([0x22])),
            ],
        )
        self.assertIn(("command", driver.CMD_DISPLAY_INVERT_ON), events)
        self.assertIn(
            ("data", driver.CMD_MEMORY_ACCESS, bytes([0x88])),
            events,
        )
        self.assertIn(
            ("data", driver.CMD_INTERFACE_PIXEL_FORMAT, bytes([0x05])),
            events,
        )
        self.assertIn(
            ("data", driver.CMD_POWER_CONTROL_1, bytes([0x13])),
            events,
        )
        self.assertIn(
            ("data", driver.CMD_POWER_CONTROL_2, bytes([0x13])),
            events,
        )
        self.assertIn(
            ("data", driver.CMD_POWER_CONTROL_3, bytes([0x22])),
            events,
        )
        self.assertNotIn(("data", 0xEB, bytes([0x14])), events)
        mock_sleep.assert_any_call(0.120)
        mock_sleep.assert_any_call(0.020)
        self.assertIn(
            ("data", driver.CMD_COLUMN_ADDR, b"\x00\x00\x00\xef"),
            events,
        )
        self.assertIn(
            ("data", driver.CMD_ROW_ADDR, b"\x00\x00\x00\xef"),
            events,
        )

    def test_set_madctl_rewrites_register_after_init(self):
        """Changing MADCTL after init should update the register immediately."""
        driver = GC9A01_SPI()
        driver.initialized = True

        with mock.patch.object(driver, "_write_command_data") as mock_write:
            driver.set_madctl("0x08")

        self.assertEqual(driver.madctl, 0x08)
        mock_write.assert_called_once_with(driver.CMD_MEMORY_ACCESS, bytes([0x08]))

    def test_send_command_supports_optional_payload_and_delay(self):
        """Generic command sending should support data payloads and delays."""
        driver = GC9A01_SPI()

        with mock.patch.object(driver, "_write_command") as mock_command, mock.patch.object(
            driver, "_write_command_data"
        ) as mock_command_data, mock.patch.object(gc9a01_module.time, "sleep") as mock_sleep:
            driver.send_command(0x23)
            driver.send_command(0x51, b"\x80", delay_s=0.01)

        mock_command.assert_called_once_with(0x23)
        mock_command_data.assert_called_once_with(0x51, b"\x80")
        mock_sleep.assert_called_once_with(0.01)

    def test_display_control_helpers_emit_expected_commands(self):
        """High-level display controls should map to the controller command set."""
        driver = GC9A01_SPI()

        with mock.patch.object(driver, "send_command") as mock_send:
            driver.software_reset()
            driver.sleep_in()
            driver.sleep_out()
            driver.display_off()
            driver.display_on()
            driver.set_inversion(True)
            driver.set_inversion(False)
            driver.set_all_pixels(True)
            driver.set_all_pixels(False)
            driver.normal_mode_on()

        self.assertEqual(
            mock_send.call_args_list,
            [
                mock.call(driver.CMD_RESET, delay_s=driver.RESET_STABILIZE_S),
                mock.call(driver.CMD_SLEEP_IN),
                mock.call(driver.CMD_SLEEP_OUT, delay_s=driver.SLEEP_OUT_DELAY_S),
                mock.call(driver.CMD_DISPLAY_OFF),
                mock.call(driver.CMD_DISPLAY_ON, delay_s=driver.DISPLAY_ON_DELAY_S),
                mock.call(driver.CMD_DISPLAY_INVERT_ON),
                mock.call(driver.CMD_DISPLAY_INVERT_OFF),
                mock.call(driver.CMD_ALL_PIXELS_ON),
                mock.call(driver.CMD_ALL_PIXELS_OFF),
                mock.call(driver.CMD_NORMAL_ON),
            ],
        )
        self.assertFalse(driver.initialized)


if __name__ == "__main__":
    unittest.main()
