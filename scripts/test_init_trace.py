#!/usr/bin/env python3
"""Trace the complete initialization sequence with detailed logging.

Shows every command and parameter sent to the display.
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


class TracingDisplay(GC9A01_SPI):
    """Display driver with detailed command tracing."""
    
    def _write_command(self, cmd):
        """Override to trace commands."""
        logger.info(f"  → CMD: 0x{cmd:02X}")
        super()._write_command(cmd)
    
    def _write_command_data(self, cmd, data):
        """Override to trace command+data."""
        data_hex = ' '.join(f'{b:02X}' for b in data)
        logger.info(f"  → CMD: 0x{cmd:02X} | DATA: {data_hex}")
        super()._write_command_data(cmd, data)


def main():
    """Run initialization with full tracing."""
    logger.info("")
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║      GC9A01 Display - Initialization Sequence Trace       ║")
    logger.info("║       Shows every command/parameter sent to display       ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    logger.info("")
    
    try:
        logger.info("Creating display instance...")
        display = TracingDisplay(
            spi_bus=0,
            spi_device=0,
            spi_speed=1000000,  # Start slow
            dc_pin=4,
            reset_pin=2,
            cs_pin=5
        )
        
        logger.info("Connecting to SPI...")
        display.connect()
        logger.info("✓ Connected")
        
        logger.info("")
        logger.info("Starting initialization sequence...")
        logger.info("=" * 70)
        
        display.init_display()
        
        logger.info("=" * 70)
        logger.info("✓ Initialization complete!")
        logger.info("")
        logger.info("If you see this message, initialization succeeded.")
        logger.info("Check the display to see if it's showing content.")
        logger.info("")
        
        # Keep display on for inspection
        logger.info("Keeping display initialized for 10 seconds...")
        time.sleep(10)
        
        display.disconnect()
        return 0
        
    except Exception as e:
        logger.error(f"✗ Initialization failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
