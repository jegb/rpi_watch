#!/usr/bin/env python3
"""Test solid colors to diagnose addressing/format issues."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
from rpi_watch.display.gc9a01_spi import GC9A01_SPI
from rpi_watch.utils import setup_logging

setup_logging('INFO')
logger = logging.getLogger(__name__)


def test_colors():
    """Test solid color fills."""
    try:
        logger.info("")
        logger.info("╔════════════════════════════════════════════════════════════╗")
        logger.info("║      GC9A01 Display - Color Fill Test                     ║")
        logger.info("║   Testing memory addressing with solid colors             ║")
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
        display.init_display()
        
        # Define colors in RGB565 format
        colors = {
            'WHITE':  (0xFF, 0xFF),
            'BLACK':  (0x00, 0x00),
            'RED':    (0xF8, 0x00),
            'GREEN':  (0x07, 0xE0),
            'BLUE':   (0x00, 0x1F),
        }
        
        for color_name, (byte1, byte2) in colors.items():
            logger.info(f"Filling display with {color_name}...")
            
            # Set address window to full screen
            display.set_address_window(0, 0, 239, 239)
            
            # Create pixel data (240x240 pixels * 2 bytes per pixel)
            pixel_data = bytes([byte1, byte2]) * (240 * 240)
            
            # Write to display
            display._write_command(0x2C)  # Memory write command
            display._write_data(pixel_data)
            
            logger.info(f"  {color_name} displayed for 3 seconds...")
            time.sleep(3)
        
        logger.info("")
        logger.info("✓ Color test complete!")
        logger.info("")
        logger.info("Results:")
        logger.info("- If colors fill entire circle: Addressing is CORRECT")
        logger.info("- If vertical strips remain: Column addressing issue")
        logger.info("- If horizontal lines: Row addressing issue")
        logger.info("")
        
        display.disconnect()
        return 0
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(test_colors())
