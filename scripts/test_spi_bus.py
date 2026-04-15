#!/usr/bin/env python3
"""Test SPI bus connectivity and display communication.

Step-by-step testing:
1. Check SPI bus availability
2. Test GPIO pin configuration
3. Test SPI communication
4. Test display reset sequence
5. Test address window setup
6. Test payload transfer
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import time

from rpi_watch.display.gc9a01_spi import GC9A01_SPI
from rpi_watch.utils import setup_logging

setup_logging('INFO')
logger = logging.getLogger(__name__)


class SPITestSuite:
    """Comprehensive SPI bus testing suite."""

    def __init__(self, spi_bus=0, spi_device=0, dc_pin=24, reset_pin=25, cs_pin=8):
        """Initialize test suite.

        Args:
            spi_bus: SPI bus number
            spi_device: SPI device number
            dc_pin: GPIO Data/Command pin
            reset_pin: GPIO Reset pin
            cs_pin: GPIO Chip Select pin
        """
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.cs_pin = cs_pin

        self.display = None
        self.results = []

    def run_all_tests(self) -> bool:
        """Run all tests in sequence.

        Returns:
            bool: True if all tests passed
        """
        logger.info("=" * 70)
        logger.info("RPi Watch - SPI Bus & Display Communication Test Suite")
        logger.info("=" * 70)

        tests = [
            ("SPI Bus Detection", self.test_spi_bus_detection),
            ("GPIO Pin Configuration", self.test_gpio_configuration),
            ("SPI Connection", self.test_spi_connection),
            ("Display Reset Sequence", self.test_display_reset),
            ("Address Window Setup", self.test_address_window),
            ("Payload Transfer (small)", self.test_small_payload),
            ("Payload Transfer (medium)", self.test_medium_payload),
            ("Full Frame Transfer", self.test_full_frame),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            logger.info(f"\n{'─' * 70}")
            logger.info(f"Test: {test_name}")
            logger.info('─' * 70)

            try:
                result = test_func()
                status = "✅ PASSED" if result else "❌ FAILED"
                logger.info(f"{status}: {test_name}")

                if result:
                    passed += 1
                else:
                    failed += 1

                self.results.append((test_name, result))

            except Exception as e:
                logger.error(f"❌ EXCEPTION: {test_name}")
                logger.error(f"Error: {e}", exc_info=True)
                failed += 1
                self.results.append((test_name, False))

        # Summary
        logger.info(f"\n{'=' * 70}")
        logger.info("TEST SUMMARY")
        logger.info('=' * 70)
        logger.info(f"Passed: {passed}/{len(tests)}")
        logger.info(f"Failed: {failed}/{len(tests)}")

        for test_name, result in self.results:
            status = "✅" if result else "❌"
            logger.info(f"  {status} {test_name}")

        logger.info('=' * 70)

        # Cleanup
        if self.display:
            try:
                self.display.disconnect()
            except:
                pass

        return failed == 0

    def test_spi_bus_detection(self) -> bool:
        """Test 1: SPI bus detection."""
        logger.info("Checking for SPI bus availability...")

        try:
            import spidev
            logger.info("✓ spidev library available")
        except ImportError:
            logger.error("✗ spidev not installed")
            logger.error("Install with: pip install spidev")
            return False

        try:
            import RPi.GPIO as GPIO
            logger.info("✓ RPi.GPIO library available")
        except ImportError:
            logger.error("✗ RPi.GPIO not installed")
            logger.error("Install with: pip install RPi.GPIO")
            return False

        # Check SPI device files
        try:
            spi_test = spidev.SpiDev()
            spi_test.open(self.spi_bus, self.spi_device)
            logger.info(f"✓ SPI device /dev/spidev{self.spi_bus}.{self.spi_device} accessible")

            # Get SPI settings
            max_speed = spi_test.max_speed_hz
            mode = spi_test.mode
            logger.info(f"  SPI Mode: {mode}")
            logger.info(f"  Max Speed: {max_speed}")

            spi_test.close()
            return True

        except FileNotFoundError:
            logger.error(f"✗ SPI device /dev/spidev{self.spi_bus}.{self.spi_device} not found")
            logger.error("Is SPI enabled? Run: sudo raspi-config → Interfacing → SPI")
            return False
        except Exception as e:
            logger.error(f"✗ Error accessing SPI: {e}")
            return False

    def test_gpio_configuration(self) -> bool:
        """Test 2: GPIO pin configuration."""
        logger.info(f"Configuring GPIO pins...")
        logger.info(f"  DC pin: GPIO {self.dc_pin}")
        logger.info(f"  RST pin: GPIO {self.reset_pin}")
        logger.info(f"  CS pin: GPIO {self.cs_pin}")

        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Setup pins
            GPIO.setup(self.dc_pin, GPIO.OUT)
            GPIO.setup(self.reset_pin, GPIO.OUT)
            if self.cs_pin is not None:
                GPIO.setup(self.cs_pin, GPIO.OUT)

            logger.info("✓ GPIO pins configured successfully")

            # Test pin output
            logger.info("Testing pin outputs...")
            GPIO.output(self.dc_pin, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(self.dc_pin, GPIO.HIGH)
            logger.info("✓ DC pin toggle successful")

            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(self.reset_pin, GPIO.LOW)
            time.sleep(0.05)
            GPIO.output(self.reset_pin, GPIO.HIGH)
            logger.info("✓ RST pin toggle successful")

            return True

        except Exception as e:
            logger.error(f"✗ GPIO configuration failed: {e}")
            return False

    def test_spi_connection(self) -> bool:
        """Test 3: SPI connection and initialization."""
        logger.info("Creating SPI display driver...")

        try:
            self.display = GC9A01_SPI(
                spi_bus=self.spi_bus,
                spi_device=self.spi_device,
                spi_speed=10000000,  # 10 MHz
                dc_pin=self.dc_pin,
                reset_pin=self.reset_pin,
                cs_pin=self.cs_pin,
            )

            logger.info("✓ Driver instance created")

            # Connect to SPI
            logger.info("Connecting to SPI bus...")
            self.display.connect()
            logger.info("✓ SPI bus connected")

            return True

        except Exception as e:
            logger.error(f"✗ SPI connection failed: {e}")
            return False

    def test_display_reset(self) -> bool:
        """Test 4: Display reset sequence."""
        if not self.display:
            logger.error("Display not connected")
            return False

        logger.info("Testing display reset sequence...")

        try:
            result = self.display.test_spi_communication()
            if result:
                logger.info("✓ Reset sequence successful")
            else:
                logger.error("✗ Reset sequence failed")
            return result

        except Exception as e:
            logger.error(f"✗ Reset test failed: {e}")
            return False

    def test_address_window(self) -> bool:
        """Test 5: Address window setup."""
        if not self.display:
            logger.error("Display not connected")
            return False

        logger.info("Testing address window setup...")

        try:
            result = self.display.test_address_setup()
            if result:
                logger.info("✓ Address window setup successful")
            else:
                logger.error("✗ Address window setup failed")
            return result

        except Exception as e:
            logger.error(f"✗ Address window test failed: {e}")
            return False

    def test_small_payload(self) -> bool:
        """Test 6: Small payload transfer (1 KB)."""
        if not self.display:
            logger.error("Display not connected")
            return False

        logger.info("Testing small payload transfer...")

        try:
            result = self.display.test_payload_transfer(size_bytes=1024)
            return result

        except Exception as e:
            logger.error(f"✗ Small payload test failed: {e}")
            return False

    def test_medium_payload(self) -> bool:
        """Test 7: Medium payload transfer (32 KB)."""
        if not self.display:
            logger.error("Display not connected")
            return False

        logger.info("Testing medium payload transfer...")

        try:
            result = self.display.test_payload_transfer(size_bytes=32768)
            return result

        except Exception as e:
            logger.error(f"✗ Medium payload test failed: {e}")
            return False

    def test_full_frame(self) -> bool:
        """Test 8: Full frame transfer (240x240 RGB565)."""
        if not self.display:
            logger.error("Display not connected")
            return False

        logger.info("Testing full frame transfer...")

        try:
            # Initialize display first
            logger.info("Initializing display for frame transfer test...")
            self.display.init_display()
            logger.info("✓ Display initialized")

            # Test full frame transfer
            result = self.display.test_full_frame_transfer()
            return result

        except Exception as e:
            logger.error(f"✗ Full frame test failed: {e}")
            return False


def main():
    """Run SPI bus test suite."""
    try:
        # Create test suite with Raspberry Pi pin configuration
        suite = SPITestSuite(
            spi_bus=0,
            spi_device=0,
            dc_pin=24,           # GPIO 24: Data/Command
            reset_pin=25,        # GPIO 25: Reset
            cs_pin=8,            # GPIO 8: Chip Select (optional)
        )

        # Run tests
        success = suite.run_all_tests()

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
