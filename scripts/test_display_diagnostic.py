#!/usr/bin/env python3
"""Diagnostic test for dark display issue.

Tests individual display components to identify why display remains dark.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
from rpi_watch.display.gc9a01_spi import GC9A01_SPI
from rpi_watch.utils import setup_logging

setup_logging('DEBUG')
logger = logging.getLogger(__name__)

def test_gpio_pins():
    """Test DC and RST pins are toggling."""
    logger.info("=" * 70)
    logger.info("TEST 1: GPIO Pin Toggling")
    logger.info("=" * 70)

    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        dc_pin = 24
        rst_pin = 25

        GPIO.setup(dc_pin, GPIO.OUT)
        GPIO.setup(rst_pin, GPIO.OUT)

        logger.info(f"Testing DC pin (GPIO {dc_pin})...")
        for i in range(5):
            GPIO.output(dc_pin, GPIO.HIGH)
            logger.info(f"  DC HIGH (iteration {i+1})")
            time.sleep(0.2)
            GPIO.output(dc_pin, GPIO.LOW)
            logger.info(f"  DC LOW")
            time.sleep(0.2)

        logger.info(f"Testing RST pin (GPIO {rst_pin})...")
        for i in range(3):
            GPIO.output(rst_pin, GPIO.LOW)
            logger.info(f"  RST LOW (iteration {i+1})")
            time.sleep(0.3)
            GPIO.output(rst_pin, GPIO.HIGH)
            logger.info(f"  RST HIGH")
            time.sleep(0.3)

        GPIO.cleanup()
        logger.info("✓ GPIO pins toggled successfully\n")
        return True

    except Exception as e:
        logger.error(f"✗ GPIO test failed: {e}\n")
        return False


def test_spi_data_transfer():
    """Test SPI data transfer with visibility."""
    logger.info("=" * 70)
    logger.info("TEST 2: SPI Data Transfer")
    logger.info("=" * 70)

    try:
        display = GC9A01_SPI(
            spi_bus=0, spi_device=0, spi_speed=10000000, dc_pin=24, reset_pin=25, cs_pin=8
        )
        display.connect()

        logger.info("Sending test SPI data (0xAA 0x55 pattern)...")
        test_data = bytes([0xAA, 0x55] * 512)  # 1KB test pattern

        # Set DC high (data mode)
        import RPi.GPIO as GPIO
        GPIO.output(24, GPIO.HIGH)

        display.spi.writebytes(list(test_data))
        logger.info("✓ SPI data transfer completed\n")

        display.disconnect()
        return True

    except Exception as e:
        logger.error(f"✗ SPI test failed: {e}\n")
        return False


def test_display_initialization():
    """Test full display initialization with all steps."""
    logger.info("=" * 70)
    logger.info("TEST 3: Display Initialization Sequence")
    logger.info("=" * 70)

    try:
        display = GC9A01_SPI(
            spi_bus=0, spi_device=0, spi_speed=10000000, dc_pin=24, reset_pin=25, cs_pin=8
        )
        display.connect()

        logger.info("Step 1: Run GC9A01 SPI init sequence...")
        display.init_display()

        logger.info("✓ Display initialization completed\n")

        logger.info("Step 2: Sending white frame (all pixels on)...")
        white_frame = bytes([0xFF, 0xFF] * (240 * 240))  # All white in RGB565
        display.set_address_window(0, 0, 239, 239)
        display._write_command(0x2C)  # CMD_WRITE_RAM
        display._write_data(white_frame)

        logger.info("✓ White frame sent (display should show white)\n")

        display.disconnect()
        return True

    except Exception as e:
        logger.error(f"✗ Initialization test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_color_output():
    """Test various color outputs."""
    logger.info("=" * 70)
    logger.info("TEST 4: Color Output Test")
    logger.info("=" * 70)

    try:
        display = GC9A01_SPI(
            spi_bus=0, spi_device=0, spi_speed=10000000, dc_pin=24, reset_pin=25, cs_pin=8
        )
        display.connect()
        display.init_display()

        # RGB565 color definitions
        BLACK = bytes([0x00, 0x00])
        RED = bytes([0xF8, 0x00])
        GREEN = bytes([0x07, 0xE0])
        BLUE = bytes([0x00, 0x1F])
        WHITE = bytes([0xFF, 0xFF])

        colors = [
            (WHITE, "WHITE"),
            (RED, "RED"),
            (GREEN, "GREEN"),
            (BLUE, "BLUE"),
            (BLACK, "BLACK"),
        ]

        for color_bytes, color_name in colors:
            logger.info(f"Displaying {color_name}...")
            frame = color_bytes * (240 * 240)
            display.set_address_window(0, 0, 239, 239)
            display._write_command(0x2C)
            display._write_data(bytes(frame))
            time.sleep(2)

        logger.info("✓ Color output test completed\n")
        display.disconnect()
        return True

    except Exception as e:
        logger.error(f"✗ Color test failed: {e}\n")
        return False


def main():
    """Run all diagnostic tests."""
    logger.info("")
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║         GC9A01 Display - Diagnostic Test Suite            ║")
    logger.info("║              Troubleshoot Dark Display Issue              ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    logger.info("")

    results = []

    # Run tests
    results.append(("GPIO Toggling", test_gpio_pins()))
    results.append(("SPI Data Transfer", test_spi_data_transfer()))
    results.append(("Display Initialization", test_display_initialization()))
    results.append(("Color Output", test_color_output()))

    # Summary
    logger.info("=" * 70)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 70)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info("")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    if passed == total:
        logger.info(f"✓ ALL TESTS PASSED ({passed}/{total})")
        logger.info("")
        logger.info("If display is still dark after all tests pass, check:")
        logger.info("  1. BLK pin (Pin 8) is tied to 3.3V (not floating)")
        logger.info("  2. Display power and ground connections")
        logger.info("  3. Try different SPI speed (5 MHz or 20 MHz)")
        logger.info("  4. Check if display variant needs different init sequence")
        return 0
    else:
        logger.info(f"✗ TESTS FAILED ({total - passed} failures)")
        logger.info("")
        logger.info("Fix the failed tests above and try again")
        return 1


if __name__ == "__main__":
    sys.exit(main())
