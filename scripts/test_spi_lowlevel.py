#!/usr/bin/env python3
"""Low-level SPI and GPIO diagnostics for GC9A01 display.

Tests individual components at hardware level to isolate connection issues.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import struct

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import spidev
except ImportError:
    logger.error("spidev not installed. Install via: pip install spidev")
    sys.exit(1)

try:
    import RPi.GPIO as GPIO
except ImportError:
    logger.error("RPi.GPIO not installed. Install via: pip install RPi.GPIO")
    sys.exit(1)


class DisplayDiagnostics:
    """Low-level hardware diagnostics for GC9A01 display."""
    
    def __init__(self, spi_bus=0, spi_device=0, spi_speed=1000000, 
                 dc_pin=4, reset_pin=2, cs_pin=5):
        """Initialize diagnostic interface."""
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.spi_speed = spi_speed
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.cs_pin = cs_pin
        
        self.spi = None
        self.bytes_sent = 0
        self.bytes_received = 0
        
    def setup_gpio(self):
        """Setup GPIO pins."""
        logger.info("=" * 70)
        logger.info("STEP 1: GPIO Configuration")
        logger.info("=" * 70)
        
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        except RuntimeError as e:
            logger.debug(f"GPIO mode already set: {e}")
            GPIO.setwarnings(False)
        
        try:
            GPIO.setup(self.dc_pin, GPIO.OUT, initial=GPIO.LOW)
            logger.info(f"✓ DC pin (GPIO {self.dc_pin}) configured as OUTPUT")
        except Exception as e:
            logger.error(f"✗ Failed to setup DC pin: {e}")
            return False
        
        try:
            GPIO.setup(self.reset_pin, GPIO.OUT, initial=GPIO.HIGH)
            logger.info(f"✓ Reset pin (GPIO {self.reset_pin}) configured as OUTPUT")
        except Exception as e:
            logger.error(f"✗ Failed to setup Reset pin: {e}")
            return False
        
        try:
            # Note: CS is typically tied to GND, so we don't control it
            # If you have it on GPIO, uncomment the line below
            # GPIO.setup(self.cs_pin, GPIO.OUT, initial=GPIO.HIGH)
            logger.info(f"⚠ CS pin (GPIO {self.cs_pin}) - assuming tied to GND (not controlled)")
        except Exception as e:
            logger.error(f"✗ Failed to setup CS pin: {e}")
            return False
        
        logger.info("")
        return True
    
    def test_gpio_toggling(self):
        """Test that GPIO pins can toggle."""
        logger.info("=" * 70)
        logger.info("STEP 2: GPIO Pin Toggling Test")
        logger.info("=" * 70)
        
        try:
            # Test DC pin
            logger.info(f"Testing DC pin (GPIO {self.dc_pin})...")
            for i in range(3):
                GPIO.output(self.dc_pin, GPIO.HIGH)
                time.sleep(0.05)
                state = GPIO.input(self.dc_pin)
                logger.debug(f"  DC HIGH → Read: {state}")
                if state != GPIO.HIGH:
                    logger.error(f"✗ DC pin not reading HIGH after write!")
                    return False
                
                GPIO.output(self.dc_pin, GPIO.LOW)
                time.sleep(0.05)
                state = GPIO.input(self.dc_pin)
                logger.debug(f"  DC LOW → Read: {state}")
                if state != GPIO.LOW:
                    logger.error(f"✗ DC pin not reading LOW after write!")
                    return False
            
            logger.info(f"✓ DC pin toggling works")
            
            # Test Reset pin
            logger.info(f"Testing Reset pin (GPIO {self.reset_pin})...")
            for i in range(3):
                GPIO.output(self.reset_pin, GPIO.LOW)
                time.sleep(0.05)
                state = GPIO.input(self.reset_pin)
                logger.debug(f"  RST LOW → Read: {state}")
                
                GPIO.output(self.reset_pin, GPIO.HIGH)
                time.sleep(0.05)
                state = GPIO.input(self.reset_pin)
                logger.debug(f"  RST HIGH → Read: {state}")
            
            logger.info(f"✓ Reset pin toggling works")

            logger.info(f"⚠ CS pin (GPIO {self.cs_pin}) tied to GND - skipping toggle test")
            logger.info("")
            return True
            
        except Exception as e:
            logger.error(f"✗ GPIO toggling test failed: {e}")
            return False
    
    def setup_spi(self):
        """Setup SPI interface."""
        logger.info("=" * 70)
        logger.info("STEP 3: SPI Interface Setup")
        logger.info("=" * 70)
        
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            logger.info(f"✓ SPI opened: /dev/spidev{self.spi_bus}.{self.spi_device}")
            
            self.spi.max_speed_hz = self.spi_speed
            self.spi.mode = 0  # CPOL=0, CPHA=0
            self.spi.bits_per_word = 8
            self.spi.lsbfirst = False
            
            logger.info(f"✓ SPI configured:")
            logger.info(f"  - Speed: {self.spi_speed / 1e6:.1f} MHz")
            logger.info(f"  - Mode: 0 (CPOL=0, CPHA=0)")
            logger.info(f"  - Bits: 8")
            logger.info(f"  - LSB First: False")
            logger.info("")
            return True
            
        except Exception as e:
            logger.error(f"✗ SPI setup failed: {e}")
            return False
    
    def test_spi_write(self, data_bytes, description=""):
        """Send data over SPI and log it."""
        try:
            if isinstance(data_bytes, (list, tuple)):
                data = list(data_bytes)
            else:
                data = list(data_bytes)
            
            hex_str = ' '.join(f'{b:02X}' for b in data)
            logger.debug(f"SPI WRITE: {hex_str} {description}")
            
            self.spi.writebytes(data)
            self.bytes_sent += len(data)
            return True
            
        except Exception as e:
            logger.error(f"✗ SPI write failed: {e}")
            return False
    
    def test_spi_read(self, length, description=""):
        """Read data from SPI."""
        try:
            data = self.spi.readbytes(length)
            hex_str = ' '.join(f'{b:02X}' for b in data)
            logger.debug(f"SPI READ: {hex_str} {description}")
            self.bytes_received += len(data)
            return data
            
        except Exception as e:
            logger.error(f"✗ SPI read failed: {e}")
            return None
    
    def test_display_id(self):
        """Try to read display ID register (0x04)."""
        logger.info("=" * 70)
        logger.info("STEP 4: Display ID Register Test")
        logger.info("=" * 70)
        
        try:
            # Set DC to command mode (0 = command)
            GPIO.output(self.dc_pin, GPIO.LOW)
            time.sleep(0.01)
            
            # Send read display ID command (0x04)
            logger.info("Sending Display ID command (0x04)...")
            self.test_spi_write([0x04], "- Read Display ID")
            time.sleep(0.05)
            
            # Set DC to data mode (1 = data)
            GPIO.output(self.dc_pin, GPIO.HIGH)
            time.sleep(0.01)
            
            # Try to read response (should be 3 bytes: dummy + 2 ID bytes)
            logger.info("Reading response...")
            response = self.test_spi_read(4, "- Display ID response")
            
            if response and any(b != 0x00 for b in response):
                logger.info(f"✓ Display responded with data: {' '.join(f'{b:02X}' for b in response)}")
                logger.info("")
                return True
            else:
                logger.warning(f"⚠ Display returned zeros or no response")
                logger.info("")
                return False
                
        except Exception as e:
            logger.error(f"✗ Display ID test failed: {e}")
            logger.info("")
            return False
    
    def test_reset_sequence(self):
        """Test hardware reset sequence."""
        logger.info("=" * 70)
        logger.info("STEP 5: Hardware Reset Sequence Test")
        logger.info("=" * 70)
        
        try:
            # Initial state
            logger.info("Initial: RST HIGH")
            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(0.05)
            
            # Pull low
            logger.info("Step 1: RST LOW (50ms)")
            GPIO.output(self.reset_pin, GPIO.LOW)
            time.sleep(0.050)
            
            # Pull high
            logger.info("Step 2: RST HIGH (150ms)")
            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(0.150)
            
            logger.info("✓ Reset sequence completed")
            logger.info("")
            return True
            
        except Exception as e:
            logger.error(f"✗ Reset sequence failed: {e}")
            logger.info("")
            return False
    
    def test_basic_commands(self):
        """Send basic commands and verify no SPI errors."""
        logger.info("=" * 70)
        logger.info("STEP 6: Basic Command Sequence Test")
        logger.info("=" * 70)
        
        try:
            # Set DC to command mode
            GPIO.output(self.dc_pin, GPIO.LOW)
            time.sleep(0.01)
            
            commands = [
                (0x01, "Software Reset"),
                (0x11, "Sleep Out"),
                (0x13, "Normal Mode"),
                (0x29, "Display ON"),
            ]
            
            for cmd, name in commands:
                logger.info(f"Sending {name} (0x{cmd:02X})...")
                self.test_spi_write([cmd], f"- {name}")
                time.sleep(0.05)
            
            logger.info(f"✓ All commands sent successfully")
            logger.info(f"  Total bytes sent: {self.bytes_sent}")
            logger.info("")
            return True
            
        except Exception as e:
            logger.error(f"✗ Basic command test failed: {e}")
            logger.info("")
            return False
    
    def test_data_write(self):
        """Test writing pixel data."""
        logger.info("=" * 70)
        logger.info("STEP 7: Pixel Data Write Test")
        logger.info("=" * 70)
        
        try:
            # Set DC to data mode
            GPIO.output(self.dc_pin, GPIO.HIGH)
            time.sleep(0.01)
            
            # Write test pattern (white pixels: 0xFF, 0xFF)
            test_data = bytes([0xFF, 0xFF] * 100)  # 100 pixels (white)
            
            logger.info(f"Writing {len(test_data)} bytes of white pixels...")
            self.test_spi_write(test_data, "- White pixel data")
            
            logger.info(f"✓ Pixel data written successfully")
            logger.info(f"  Total bytes sent: {self.bytes_sent}")
            logger.info("")
            return True
            
        except Exception as e:
            logger.error(f"✗ Data write test failed: {e}")
            logger.info("")
            return False
    
    def run_all_tests(self):
        """Run all diagnostic tests."""
        logger.info("")
        logger.info("╔════════════════════════════════════════════════════════════╗")
        logger.info("║      GC9A01 Display - Low-Level Hardware Diagnostics      ║")
        logger.info("╚════════════════════════════════════════════════════════════╝")
        logger.info("")
        
        results = []
        
        # Test 1: GPIO Setup
        if not self.setup_gpio():
            logger.error("GPIO setup failed, cannot continue")
            return 1
        
        # Test 2: GPIO Toggling
        results.append(("GPIO Toggling", self.test_gpio_toggling()))
        
        # Test 3: SPI Setup
        if not self.setup_spi():
            logger.error("SPI setup failed, cannot continue")
            return 1
        
        # Test 4: Display ID
        results.append(("Display ID Read", self.test_display_id()))
        
        # Test 5: Reset Sequence
        results.append(("Reset Sequence", self.test_reset_sequence()))
        
        # Test 6: Basic Commands
        results.append(("Basic Commands", self.test_basic_commands()))
        
        # Test 7: Data Write
        results.append(("Data Write", self.test_data_write()))
        
        # Summary
        logger.info("=" * 70)
        logger.info("DIAGNOSTIC SUMMARY")
        logger.info("=" * 70)
        
        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{status}: {test_name}")
        
        logger.info("")
        logger.info(f"Total SPI bytes sent: {self.bytes_sent}")
        logger.info(f"Total SPI bytes received: {self.bytes_received}")
        logger.info("")
        
        passed = sum(1 for _, r in results if r)
        total = len(results)
        
        if passed == total:
            logger.info(f"✓ ALL TESTS PASSED ({passed}/{total})")
            logger.info("")
            logger.info("Next steps:")
            logger.info("1. If Display ID read failed: Check SPI wiring (CLK, MOSI)")
            logger.info("2. If Display ID succeeded: Display is communicating!")
            logger.info("3. Run full display test: python3 scripts/test_display_live.py")
            return 0
        else:
            logger.info(f"✗ SOME TESTS FAILED ({total - passed} failures)")
            logger.info("")
            if not results[0][1]:  # GPIO failed
                logger.info("GPIO test failed: Check pin numbers in config")
            if not results[2][1]:  # Reset failed
                logger.info("Reset test failed: Check RST pin connection")
            if not results[3][1]:  # Display ID failed
                logger.info("Display ID failed: Check SPI wiring (CLK/MOSI pins)")
            return 1
        
        # Cleanup
        GPIO.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        try:
            if self.spi:
                self.spi.close()
            GPIO.cleanup()
        except:
            pass


def main():
    """Run diagnostics."""
    diag = DisplayDiagnostics(
        spi_bus=0,
        spi_device=0,
        spi_speed=1000000,  # Start slow: 1 MHz
        dc_pin=4,
        reset_pin=2,
        cs_pin=5
    )
    
    try:
        return diag.run_all_tests()
    finally:
        diag.cleanup()


if __name__ == "__main__":
    sys.exit(main())
