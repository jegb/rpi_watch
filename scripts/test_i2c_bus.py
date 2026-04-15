#!/usr/bin/env python3
"""Test I2C bus connectivity and display detection.

Verifies that the I2C bus is accessible and can communicate with the GC9A01 display.
Run this before running the main application.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
from rpi_watch.utils import setup_logging

setup_logging('INFO')
logger = logging.getLogger(__name__)


def test_i2c_bus_access():
    """Test basic I2C bus access."""
    try:
        import smbus2
        logger.info("✓ smbus2 library available")
        return True
    except ImportError:
        logger.error("✗ smbus2 not installed. Install via: pip install smbus2")
        return False


def test_i2c_device_detection(bus_num: int = 1, address: int = 0x3C):
    """Test detection of I2C device.

    Args:
        bus_num: I2C bus number
        address: I2C address to test (default 0x3C for GC9A01)

    Returns:
        True if device detected, False otherwise
    """
    try:
        import smbus2
        logger.info(f"Scanning I2C bus {bus_num} for device at 0x{address:02X}...")

        bus = smbus2.SMBus(bus_num)
        try:
            # Try to read one byte from the device
            try:
                data = bus.read_byte(address)
                logger.info(f"✓ Device detected at 0x{address:02X}")
                return True
            except Exception as e:
                logger.warning(f"Could not read from 0x{address:02X}: {e}")
                logger.info("This is normal if the device is in a specific state.")
                logger.info("Attempting to write a test byte...")
                try:
                    bus.write_byte(address, 0x00)
                    logger.info(f"✓ Successfully wrote to 0x{address:02X}")
                    return True
                except Exception as write_e:
                    logger.error(f"✗ Could not write to 0x{address:02X}: {write_e}")
                    return False
        finally:
            bus.close()

    except FileNotFoundError:
        logger.error(f"✗ I2C bus {bus_num} not found. Is I2C enabled?")
        logger.error("Run: sudo raspi-config -> Interfacing Options -> I2C -> Enable")
        return False
    except PermissionError:
        logger.error(f"✗ Permission denied accessing I2C bus {bus_num}")
        logger.error("Try running with: sudo python3 test_i2c_bus.py")
        return False
    except Exception as e:
        logger.error(f"✗ Error accessing I2C bus: {e}")
        return False


def test_alternative_addresses(bus_num: int = 1):
    """Test common alternative I2C addresses for GC9A01.

    Args:
        bus_num: I2C bus number
    """
    common_addresses = [0x3C, 0x3D, 0x50, 0x51]

    logger.info(f"\nScanning common addresses on I2C bus {bus_num}...")

    try:
        import smbus2
        bus = smbus2.SMBus(bus_num)
        try:
            found_devices = []
            for addr in common_addresses:
                try:
                    bus.read_byte(addr)
                    found_devices.append(addr)
                    logger.info(f"✓ Device found at 0x{addr:02X}")
                except:
                    pass

            if not found_devices:
                logger.warning("✗ No devices found at common addresses")
                logger.info("If you have a display connected, check the I2C address in your hardware documentation")
            else:
                logger.info(f"Update config.yaml with i2c_address: 0x{found_devices[0]:02X}")

        finally:
            bus.close()
    except Exception as e:
        logger.error(f"Error scanning addresses: {e}")


def main():
    """Run all I2C bus tests."""
    logger.info("=" * 60)
    logger.info("RPi Watch - I2C Bus Connectivity Test")
    logger.info("=" * 60)

    # Test 1: Library availability
    if not test_i2c_bus_access():
        logger.error("\nPlease install required dependencies:")
        logger.error("  pip install smbus2")
        sys.exit(1)

    # Test 2: Device detection at default address
    if test_i2c_device_detection():
        logger.info("\n✓ I2C communication successful!")
        logger.info("You can now run the main application.")
    else:
        logger.warning("\n✗ Could not detect device at default address 0x3C")
        test_alternative_addresses()
        logger.info("\nTroubleshooting:")
        logger.info("1. Verify I2C is enabled: sudo raspi-config -> Interfacing Options -> I2C")
        logger.info("2. Verify display is powered and connected")
        logger.info("3. Check I2C address matches your hardware")
        logger.info("4. Run: i2cdetect -y 1 (if i2c-tools installed)")
        sys.exit(1)


if __name__ == '__main__':
    main()
