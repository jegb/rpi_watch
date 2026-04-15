"""SPI driver for GC9A01 circular display (240x240 RGB).

This module provides SPI communication with the GC9A01 display controller.
Handles initialization, register writes, and pixel data transmission via SPI.

Based on Adafruit_GC9A01A implementation with enhancements for Raspberry Pi.
Hardware: GC9A01 1.28" Round Display - SPI Variant (8PIN)
Reference: https://github.com/adafruit/Adafruit_GC9A01A
"""

import logging
import struct
import time
from typing import Optional, Tuple

try:
    import spidev
except ImportError:
    spidev = None

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

logger = logging.getLogger(__name__)


class GC9A01_SPI:
    """SPI driver for GC9A01 240x240 circular display (8PIN variant).

    Communicates via SPI protocol (hardware SPI on Raspberry Pi)
    to control display initialization, pixel data writes.

    Based on Adafruit's proven GC9A01 initialization sequence.
    """

    # GC9A01 Standard Commands (from datasheet)
    CMD_RESET = 0x01                # Software reset
    CMD_SLEEP_OUT = 0x11            # Exit sleep mode
    CMD_PARTIAL_ON = 0x12           # Partial display mode ON
    CMD_NORMAL_ON = 0x13            # Normal display mode ON
    CMD_DISPLAY_INVERT_ON = 0x20    # Display invert ON
    CMD_DISPLAY_INVERT_OFF = 0x21   # Display invert OFF
    CMD_DISPLAY_OFF = 0x28          # Display OFF
    CMD_DISPLAY_ON = 0x29           # Display ON
    CMD_COLUMN_ADDR = 0x2A          # Set column address window
    CMD_ROW_ADDR = 0x2B             # Set row address window
    CMD_WRITE_RAM = 0x2C            # Write to memory (RAM)
    CMD_SET_PIXEL_FORMAT = 0x3A     # Pixel format setting
    CMD_BRIGHTNESS = 0x51           # Write brightness control
    CMD_BRIGHTNESS_DISPLAY = 0x55   # Brightness control display
    CMD_GAMMA_SET = 0x26            # Gamma curve selection
    CMD_MEMORY_ACCESS = 0x36        # Memory access control (rotation)

    # GC9A01 Extended Commands (power control)
    CMD_POWER_CONTROL_1 = 0xC3      # Power control 1
    CMD_POWER_CONTROL_2 = 0xC4      # Power control 2
    CMD_POWER_CONTROL_3 = 0xC9      # Power control 3
    CMD_POSITIVE_GAMMA = 0xF0       # Positive gamma curve
    CMD_NEGATIVE_GAMMA = 0xF1       # Negative gamma curve
    CMD_INTERFACE_PIXEL_FORMAT = 0x3A # Interface pixel format
    CMD_TEARING_EFFECT = 0x35       # Tearing effect line ON
    CMD_FRAME_RATE = 0xE8           # Frame rate control
    CMD_INREGEN1 = 0xFE             # Inter register enable 1
    CMD_INREGEN2 = 0xEF             # Inter register enable 2

    def __init__(
        self,
        spi_bus: int = 0,
        spi_device: int = 0,
        spi_speed: int = 10000000,  # 10 MHz
        dc_pin: int = 24,            # Data/Command
        reset_pin: int = 25,         # Reset
        cs_pin: Optional[int] = 8,   # Chip Select (optional)
    ):
        """Initialize the GC9A01 SPI driver.

        Args:
            spi_bus: SPI bus number (0 for /dev/spidev0.x)
            spi_device: SPI device number (0 for /dev/spidev0.0)
            spi_speed: SPI clock speed in Hz (default 10 MHz)
            dc_pin: GPIO pin for Data/Command control (BCM numbering)
            reset_pin: GPIO pin for Reset control (BCM numbering)
            cs_pin: GPIO pin for Chip Select (optional, can be tied to GND)
        """
        if spidev is None:
            raise RuntimeError("spidev not installed. Install via: pip install spidev")
        if GPIO is None:
            raise RuntimeError("RPi.GPIO not installed. Install via: pip install RPi.GPIO")

        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.spi_speed = spi_speed
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.cs_pin = cs_pin

        self.width = 240
        self.height = 240
        self.rotation = 0

        self.spi = None
        self.initialized = False

        logger.info(
            f"GC9A01_SPI driver initialized (bus={spi_bus}, device={spi_device}, "
            f"speed={spi_speed/1e6:.1f}MHz, DC={dc_pin}, RST={reset_pin}, CS={cs_pin})"
        )

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def connect(self):
        """Open SPI bus connection and configure GPIO."""
        try:
            # Set up GPIO (setmode can only be called once, so catch exception if already set)
            try:
                GPIO.setmode(GPIO.BCM)
            except RuntimeError:
                # Mode already set, which is fine - just continue
                pass
            GPIO.setwarnings(False)

            # Configure pins as outputs
            GPIO.setup(self.dc_pin, GPIO.OUT)
            GPIO.setup(self.reset_pin, GPIO.OUT)
            if self.cs_pin is not None:
                GPIO.setup(self.cs_pin, GPIO.OUT)
                GPIO.output(self.cs_pin, GPIO.HIGH)  # Chip select high (inactive)

            logger.info(f"GPIO configured: DC={self.dc_pin}, RST={self.reset_pin}, CS={self.cs_pin}")

            # Open SPI
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            self.spi.max_speed_hz = self.spi_speed
            self.spi.mode = 0  # SPI mode 0 (CPOL=0, CPHA=0)
            self.spi.bits_per_word = 8
            self.spi.lsbfirst = False  # LSB first = False (MSB first)

            logger.info(
                f"Connected to SPI bus {self.spi_bus}.{self.spi_device} "
                f"at {self.spi_speed/1e6:.1f}MHz"
            )

        except Exception as e:
            logger.error(f"Failed to connect SPI: {e}")
            self.disconnect()
            raise

    def disconnect(self):
        """Close SPI bus and release GPIO."""
        if self.spi:
            try:
                self.spi.close()
                self.initialized = False
                logger.info("SPI bus closed")
            except Exception as e:
                logger.error(f"Error closing SPI: {e}")

        try:
            GPIO.cleanup()
            logger.info("GPIO released")
        except Exception as e:
            logger.error(f"Error cleaning up GPIO: {e}")

    def _write_command(self, command: int):
        """Write a command byte to the display.

        Sets DC pin low, sends command byte via SPI.

        Args:
            command: Command byte to send
        """
        if not self.spi:
            raise RuntimeError("SPI not connected. Call connect() first.")

        try:
            GPIO.output(self.dc_pin, GPIO.LOW)  # DC low = command mode
            self.spi.writebytes([command])
            GPIO.output(self.dc_pin, GPIO.HIGH)  # DC high = data mode
            logger.debug(f"Command sent: 0x{command:02X}")
        except Exception as e:
            logger.error(f"Failed to write command 0x{command:02X}: {e}")
            raise

    def _write_data(self, data: bytes):
        """Write data bytes to the display.

        Sets DC pin high, sends data via SPI.
        For large payloads, chunks data into smaller transfers.

        Args:
            data: Data bytes to send
        """
        if not self.spi:
            raise RuntimeError("SPI not connected. Call connect() first.")

        try:
            GPIO.output(self.dc_pin, GPIO.HIGH)  # DC high = data mode

            # Chunk large transfers to avoid SPI buffer issues
            # Most SPI implementations have a ~4KB buffer limit
            CHUNK_SIZE = 4096  # 4KB chunks

            if len(data) <= CHUNK_SIZE:
                # Small transfer - send directly
                self.spi.writebytes(list(data))
                logger.debug(f"Data sent: {len(data)} bytes")
            else:
                # Large transfer - send in chunks
                chunks = len(data) // CHUNK_SIZE
                remainder = len(data) % CHUNK_SIZE

                for i in range(chunks):
                    start = i * CHUNK_SIZE
                    end = start + CHUNK_SIZE
                    self.spi.writebytes(list(data[start:end]))

                if remainder > 0:
                    self.spi.writebytes(list(data[-remainder:]))

                logger.debug(f"Data sent: {len(data)} bytes ({chunks} chunks + {remainder} bytes remainder)")

        except Exception as e:
            logger.error(f"Failed to write data: {e}")
            raise

    def _write_command_data(self, command: int, data: bytes):
        """Send command followed by data.

        Args:
            command: Command byte
            data: Data bytes
        """
        self._write_command(command)
        if data:
            self._write_data(data)

    def reset(self):
        """Perform a hardware reset of the display controller."""
        if not self.spi:
            raise RuntimeError("SPI not connected. Call connect() first.")

        try:
            logger.info("Resetting display...")
            # Reset pulse: high → low → high with delays
            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(self.reset_pin, GPIO.LOW)
            time.sleep(0.05)
            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(0.15)  # Wait for reset to complete
            logger.info("Display reset complete")
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            raise

    def init_display(self):
        """Initialize the display using the complete Adafruit GC9A01A sequence.

        This is the authoritative initialization based on Adafruit's working implementation.
        Includes all critical registers and commands that were missing before.
        """
        logger.info("Initializing GC9A01 display (Complete Adafruit sequence)...")

        try:
            # ===== Hardware Reset =====
            logger.debug("Hardware reset")
            self.reset()

            # ===== Register Configuration (Manufacturer sequence) =====
            # This sequence comes from Adafruit's initialization array
            # Many registers are undocumented, but necessary for proper display function

            logger.debug("Sending undocumented register initialization (0x84-0x8F)")
            self._write_command_data(0xEB, bytes([0x14]))
            self._write_command_data(0x84, bytes([0x40]))
            self._write_command_data(0x85, bytes([0xFF]))
            self._write_command_data(0x86, bytes([0xFF]))
            self._write_command_data(0x87, bytes([0xFF]))
            self._write_command_data(0x88, bytes([0x0A]))
            self._write_command_data(0x89, bytes([0x21]))
            self._write_command_data(0x8A, bytes([0x00]))
            self._write_command_data(0x8B, bytes([0x80]))
            self._write_command_data(0x8C, bytes([0x01]))
            self._write_command_data(0x8D, bytes([0x01]))
            self._write_command_data(0x8E, bytes([0xFF]))
            self._write_command_data(0x8F, bytes([0xFF]))

            logger.debug("Configuring display orientation and color order")
            self._write_command_data(0xB6, bytes([0x00, 0x00]))
            self._write_command_data(self.CMD_MEMORY_ACCESS, bytes([0x40 | 0x08]))  # MX | BGR
            self._write_command_data(self.CMD_INTERFACE_PIXEL_FORMAT, bytes([0x05]))  # RGB565

            logger.debug("Sending more undocumented registers (0x90, 0xBD, 0xBC, 0xFF)")
            self._write_command_data(0x90, bytes([0x08, 0x08, 0x08, 0x08]))
            self._write_command_data(0xBD, bytes([0x06]))
            self._write_command_data(0xBC, bytes([0x00]))
            self._write_command_data(0xFF, bytes([0x60, 0x01, 0x04]))

            logger.debug("Configuring power control")
            self._write_command_data(0xC3, bytes([0x13]))  # Power control 1
            self._write_command_data(0xC4, bytes([0x13]))  # Power control 2
            self._write_command_data(0xC9, bytes([0x22]))  # Power control 3
            self._write_command_data(0xBE, bytes([0x11]))

            logger.debug("Sending gamma curves (Adafruit values)")
            self._write_command_data(0xE1, bytes([0x10, 0x0E]))
            self._write_command_data(0xDF, bytes([0x21, 0x0c, 0x02]))
            self._write_command_data(0xF0, bytes([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]))  # Gamma 1
            self._write_command_data(0xF1, bytes([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]))  # Gamma 2
            self._write_command_data(0xF2, bytes([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]))  # Gamma 3
            self._write_command_data(0xF3, bytes([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]))  # Gamma 4

            logger.debug("Sending timing and frame rate configuration")
            self._write_command_data(0xED, bytes([0x1B, 0x0B]))
            self._write_command_data(0xAE, bytes([0x77]))
            self._write_command_data(0xCD, bytes([0x63]))
            self._write_command_data(self.CMD_FRAME_RATE, bytes([0x34]))

            logger.debug("Sending clock divider and display control registers")
            self._write_command_data(0x62, bytes([0x18, 0x0D, 0x71, 0xED, 0x70, 0x70, 0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70]))
            self._write_command_data(0x63, bytes([0x18, 0x11, 0x71, 0xF1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xF3, 0x70, 0x70]))
            self._write_command_data(0x64, bytes([0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07]))
            self._write_command_data(0x66, bytes([0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00]))
            self._write_command_data(0x67, bytes([0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98]))
            self._write_command_data(0x74, bytes([0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00]))
            self._write_command_data(0x98, bytes([0x3e, 0x07]))

            # ===== CRITICAL: Display Control Commands =====
            logger.debug("Enabling tearing effect")
            self._write_command(self.CMD_TEARING_EFFECT)

            # ===== Sleep Out =====
            logger.debug("Exiting sleep mode")
            self._write_command(self.CMD_SLEEP_OUT)
            time.sleep(0.150)  # 150ms delay as per Adafruit

            # ===== Normal Mode =====
            logger.debug("Setting normal display mode")
            self._write_command(self.CMD_NORMAL_ON)
            time.sleep(0.010)

            # ===== Display ON =====
            logger.debug("Turning on display")
            self._write_command(self.CMD_DISPLAY_ON)
            time.sleep(0.150)  # 150ms delay as per Adafruit

            # ===== Brightness Control =====
            logger.debug("Setting brightness to maximum")
            self._write_command_data(self.CMD_BRIGHTNESS, bytes([0xFF]))  # Max brightness
            time.sleep(0.010)

            self.initialized = True
            logger.info("✓ Display initialization complete (Full Adafruit sequence)")

        except Exception as e:
            logger.error(f"Display initialization failed: {e}")
            self.initialized = False
            raise

    def set_address_window(self, x0: int, y0: int, x1: int, y1: int):
        """Set the RAM address window for pixel writing.

        Args:
            x0: Start column address (0-239)
            y0: Start row address (0-239)
            x1: End column address (0-239)
            y1: End row address (0-239)
        """
        try:
            # Set column address window (16-bit big-endian addresses)
            col_data = struct.pack('>HH', x0, x1)
            self._write_command_data(self.CMD_COLUMN_ADDR, col_data)

            # Set row address window (16-bit big-endian addresses)
            row_data = struct.pack('>HH', y0, y1)
            self._write_command_data(self.CMD_ROW_ADDR, row_data)

            logger.debug(f"Address window set: X({x0},{x1}) Y({y0},{y1})")
        except Exception as e:
            logger.error(f"Failed to set address window: {e}")
            raise

    def write_pixels(self, rgb565_data: bytes):
        """Write pixel data to the display.

        Args:
            rgb565_data: Pixel data in RGB565 format (2 bytes per pixel)
        """
        if not self.initialized:
            raise RuntimeError("Display not initialized. Call init_display() first.")

        try:
            # Set address window to full screen
            self.set_address_window(0, 0, self.width - 1, self.height - 1)

            # Write RAM command to prepare for pixel data
            self._write_command(self.CMD_WRITE_RAM)

            # Send pixel data
            self._write_data(rgb565_data)

            logger.debug(f"Wrote {len(rgb565_data)} bytes of pixel data")

        except Exception as e:
            logger.error(f"Failed to write pixels: {e}")
            raise

    def display(self, pil_image):
        """Display a PIL Image on the screen.

        Converts PIL Image to RGB565 format and sends to display.

        Args:
            pil_image: PIL Image object (should be 240x240 RGB)
        """
        if pil_image.size != (self.width, self.height):
            logger.warning(f"Image size {pil_image.size} != display size {(self.width, self.height)}")

        try:
            # Convert PIL Image to RGB565 bytes
            rgb565_data = self._convert_to_rgb565(pil_image)

            # Write to display
            self.write_pixels(rgb565_data)

        except Exception as e:
            logger.error(f"Failed to display image: {e}")
            raise

    def _convert_to_rgb565(self, pil_image) -> bytes:
        """Convert a PIL Image to RGB565 byte format.

        Args:
            pil_image: PIL Image in RGB or RGBA mode

        Returns:
            bytes: Pixel data in RGB565 format (2 bytes per pixel)
        """
        # Ensure image is in RGB mode
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Get pixel data
        pixels = pil_image.load()
        width, height = pil_image.size

        rgb565_data = bytearray()

        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y][:3]  # Get R, G, B (ignore A if present)

                # Convert to RGB565 (5-bit R, 6-bit G, 5-bit B)
                r5 = (r >> 3) & 0x1F
                g6 = (g >> 2) & 0x3F
                b5 = (b >> 3) & 0x1F

                # Pack into 16-bit value (big-endian)
                rgb565 = (r5 << 11) | (g6 << 5) | b5
                rgb565_data.extend(struct.pack('>H', rgb565))

        return bytes(rgb565_data)

    def set_rotation(self, rotation_angle: int):
        """Set display rotation.

        Args:
            rotation_angle: Rotation in degrees (0, 90, 180, 270)
        """
        if rotation_angle not in [0, 90, 180, 270]:
            raise ValueError(f"Invalid rotation angle: {rotation_angle}. Must be 0, 90, 180, or 270.")

        self.rotation = rotation_angle
        logger.info(f"Display rotation set to {rotation_angle}°")

    # ========== Testing Methods ==========

    def test_spi_communication(self) -> bool:
        """Test basic SPI communication.

        Returns:
            bool: True if communication successful
        """
        try:
            logger.info("Testing SPI communication...")
            # Send a simple command and wait for response
            self.reset()
            logger.info("✓ SPI communication test passed")
            return True
        except Exception as e:
            logger.error(f"✗ SPI communication test failed: {e}")
            return False

    def test_address_setup(self) -> bool:
        """Test address window setup.

        Returns:
            bool: True if setup successful
        """
        try:
            logger.info("Testing address window setup...")
            self.set_address_window(0, 0, 239, 239)
            logger.info("✓ Address window test passed")
            return True
        except Exception as e:
            logger.error(f"✗ Address window test failed: {e}")
            return False

    def test_payload_transfer(self, size_bytes: int = 1024) -> bool:
        """Test payload transfer via SPI.

        Args:
            size_bytes: Size of test payload in bytes

        Returns:
            bool: True if transfer successful
        """
        try:
            logger.info(f"Testing payload transfer ({size_bytes} bytes)...")
            # Create test payload
            test_data = bytes([0xAA, 0x55] * (size_bytes // 2))

            # Time the transfer
            start = time.time()
            self._write_data(test_data)
            elapsed = time.time() - start

            speed_kbps = (size_bytes / elapsed) / 1000
            logger.info(f"✓ Payload transfer test passed ({speed_kbps:.1f} KB/s)")
            return True
        except Exception as e:
            logger.error(f"✗ Payload transfer test failed: {e}")
            return False

    def test_full_frame_transfer(self) -> bool:
        """Test full frame transfer (240x240 RGB565).

        Returns:
            bool: True if transfer successful
        """
        try:
            logger.info("Testing full frame transfer (240x240 RGB565)...")
            # Create test frame (all black)
            frame_data = bytes(self.width * self.height * 2)

            # Time the transfer
            start = time.time()
            self.write_pixels(frame_data)
            elapsed = time.time() - start

            fps = 1.0 / elapsed
            logger.info(f"✓ Full frame transfer test passed ({elapsed*1000:.1f}ms, {fps:.1f} FPS)")
            return True
        except Exception as e:
            logger.error(f"✗ Full frame transfer test failed: {e}")
            return False
