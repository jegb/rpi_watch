#!/usr/bin/env python3
"""Test different MADCTL values to fix vertical strips issue."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import struct
from rpi_watch.display.gc9a01_spi import GC9A01_SPI
from rpi_watch.utils import setup_logging

setup_logging('INFO')
logger = logging.getLogger(__name__)


def test_madctl_values():
    """Test different MADCTL register values."""
    
    try:
        logger.info("")
        logger.info("╔════════════════════════════════════════════════════════════╗")
        logger.info("║      GC9A01 - MADCTL Register Test                        ║")
        logger.info("║   Testing memory access control to fix addressing         ║")
        logger.info("╚════════════════════════════════════════════════════════════╝")
        logger.info("")
        
        display = GC9A01_SPI(
            spi_bus=0,
            spi_device=0,
            spi_speed=10000000,
            dc_pin=4,
            reset_pin=2,
            cs_pin=None
        )
        
        display.connect()
        
        # MADCTL register values to test
        # Bit 7: MY (row address order)
        # Bit 6: MX (column address order)  
        # Bit 5: MV (row/column swap)
        # Bit 4: ML (vertical refresh order)
        # Bit 3: BGR (color mode)
        
        madctl_values = [
            (0x00, "Normal (MY=0, MX=0, MV=0, BGR=0)"),
            (0x40, "MX=1 (flip columns)"),
            (0x80, "MY=1 (flip rows)"),
            (0xC0, "MX=1, MY=1 (flip both)"),
            (0x20, "MV=1 (swap rows/cols)"),
            (0x60, "MV=1, MX=1"),
            (0xA0, "MV=1, MY=1"),
            (0xE0, "MV=1, MX=1, MY=1"),
            (0x08, "BGR=1 (RGB/BGR swap)"),
            (0x48, "MX=1, BGR=1"),
            (0x88, "MY=1, BGR=1"),
        ]
        
        for madctl_val, description in madctl_values:
            logger.info(f"")
            logger.info(f"Testing MADCTL = 0x{madctl_val:02X}: {description}")
            logger.info(f"Press Ctrl+C to skip to next test")
            
            # Reset display
            display.reset()
            time.sleep(0.15)
            
            # Re-initialize
            display._write_command(0x01)  # Software reset
            time.sleep(0.120)
            display._write_command(0x11)  # Sleep out
            time.sleep(0.120)
            
            # Set new MADCTL
            display._write_command_data(0x36, bytes([madctl_val]))
            
            # Set pixel format
            display._write_command_data(0x3A, bytes([0x05]))  # RGB565
            
            # Set address window
            display.set_address_window(0, 0, 239, 239)
            
            # Fill with white
            display._write_command(0x2C)
            white_data = bytes([0xFF, 0xFF]) * (240 * 240)
            display._write_data(white_data)
            
            # Display on
            display._write_command(0x13)  # Normal mode
            display._write_command(0x29)  # Display on
            time.sleep(0.150)
            
            logger.info(f"  Displaying for 2 seconds (white fill)...")
            time.sleep(2)
        
        logger.info("")
        logger.info("✓ MADCTL test complete!")
        logger.info("")
        logger.info("Which MADCTL value fixed the vertical strips?")
        logger.info("Update config.yaml with the correct value.")
        logger.info("")
        
        display.disconnect()
        return 0
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(test_madctl_values())
