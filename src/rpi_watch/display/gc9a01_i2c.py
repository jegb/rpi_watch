"""Custom I2C driver for GC9A01 circular display (240x240 RGB).

This module implements direct I2C communication with the GC9A01 display controller.
Handles initialization, register writes, and pixel data transmission.
"""

import logging
import struct
import time
from typing import Tuple

try:
    import smbus2
except ImportError:
    smbus2 = None

logger = logging.getLogger(__name__)


class GC9A01_I2C:
    """I2C driver for GC9A01 240x240 circular display.

    Communicates via SMBus (I2C protocol) to control display initialization,
    address window setup, and pixel data writes.
    """

    # GC9A01 I2C Command Register Addresses (typical values - verify with datasheet)
    # These register addresses assume a standard I2C GC9A01 implementation
    COMMAND_REGISTER = 0x00      # Register for sending commands
    DATA_REGISTER = 0x01         # Register for sending pixel data

    # GC9A01 Commands
    CMD_RESET = 0x01             # Software reset
    CMD_SLEEP_OUT = 0x11         # Exit sleep mode
    CMD_DISPLAY_ON = 0x29        # Display ON
    CMD_COLUMN_ADDR = 0x2A       # Set column address window
    CMD_ROW_ADDR = 0x2B          # Set row address window
    CMD_WRITE_RAM = 0x2C         # Write to memory (RAM)
    CMD_SET_PIXEL_FORMAT = 0x3A  # Pixel format setting (16-bit, 18-bit, etc.)
    CMD_BRIGHTNESS = 0x51        # Write brightness control
    CMD_GAMMA_SET = 0x26         # Gamma curve selection

    def __init__(self, i2c_address: int = 0x3C, i2c_bus: int = 1):
        """Initialize the GC9A01 I2C driver.

        Args:
            i2c_address: I2C slave address (typically 0x3C or 0x3D)
            i2c_bus: I2C bus number (1 for Raspberry Pi 3/4/5)
        """
        if smbus2 is None:
            raise RuntimeError("smbus2 not installed. Install via: pip install smbus2")

        self.i2c_address = i2c_address
        self.i2c_bus = i2c_bus
        self.width = 240
        self.height = 240
        self.rotation = 0

        self.bus = None
        self.initialized = False

        logger.info(f"GC9A01_I2C driver initialized (address: 0x{i2c_address:02X}, bus: {i2c_bus})")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def connect(self):
        """Open I2C bus connection."""
        try:
            self.bus = smbus2.SMBus(self.i2c_bus)
            logger.info(f"Connected to I2C bus {self.i2c_bus}")
        except Exception as e:
            logger.error(f"Failed to connect to I2C bus: {e}")
            raise

    def disconnect(self):
        """Close I2C bus connection."""
        if self.bus:
            try:
                self.bus.close()
                self.initialized = False
                logger.info("Disconnected from I2C bus")
            except Exception as e:
                logger.error(f"Error closing I2C bus: {e}")

    def _write_command(self, command: int):
        """Write a command byte to the display controller.

        Args:
            command: Command byte to send
        """
        if not self.bus:
            raise RuntimeError("I2C bus not connected. Call connect() first.")

        try:
            # Send command via I2C - write to command register
            self.bus.write_byte_data(self.i2c_address, self.COMMAND_REGISTER, command)
            logger.debug(f"Sent command: 0x{command:02X}")
        except Exception as e:
            logger.error(f"Failed to write command 0x{command:02X}: {e}")
            raise

    def _write_data(self, data: bytes):
        """Write data bytes to the display (typically pixel data).

        Args:
            data: Data bytes to send
        """
        if not self.bus:
            raise RuntimeError("I2C bus not connected. Call connect() first.")

        try:
            # Write data in chunks to handle SMBus block size limits (typically 32 bytes)
            max_chunk = 32
            for i in range(0, len(data), max_chunk):
                chunk = data[i:i + max_chunk]
                self.bus.write_i2c_block_data(
                    self.i2c_address,
                    self.DATA_REGISTER,
                    list(chunk)
                )
            logger.debug(f"Wrote {len(data)} bytes of data")
        except Exception as e:
            logger.error(f"Failed to write data: {e}")
            raise

    def _write_register(self, register: int, data: int):
        """Write a single register value.

        Args:
            register: Register address
            data: Data byte to write
        """
        if not self.bus:
            raise RuntimeError("I2C bus not connected. Call connect() first.")

        try:
            self.bus.write_byte_data(self.i2c_address, register, data)
            logger.debug(f"Wrote register 0x{register:02X} = 0x{data:02X}")
        except Exception as e:
            logger.error(f"Failed to write register: {e}")
            raise

    def reset(self):
        """Perform a software reset of the display controller."""
        logger.info("Resetting display...")
        self._write_command(self.CMD_RESET)
        time.sleep(0.15)  # Wait for reset to complete per datasheet
        logger.info("Display reset complete")

    def init_display(self):
        """Initialize the display with power-on sequence and configuration.

        Sets up the display in 16-bit RGB565 mode and enables output.
        """
        logger.info("Initializing GC9A01 display...")

        try:
            # Reset first
            self.reset()

            # Exit sleep mode
            self._write_command(self.CMD_SLEEP_OUT)
            time.sleep(0.12)

            # Set pixel format to 16-bit RGB565
            self._write_command(self.CMD_SET_PIXEL_FORMAT)
            self._write_data(bytes([0x55]))  # 0x55 = 16-bit RGB565
            time.sleep(0.01)

            # Set gamma curve (optional, uses default gamma)
            self._write_command(self.CMD_GAMMA_SET)
            self._write_data(bytes([0x01]))  # Gamma curve 1
            time.sleep(0.01)

            # Set rotation/display parameters
            self._configure_rotation()

            # Turn on display
            self._write_command(self.CMD_DISPLAY_ON)
            time.sleep(0.12)

            # Set brightness to maximum
            self._write_command(self.CMD_BRIGHTNESS)
            self._write_data(bytes([0xFF]))  # Full brightness

            self.initialized = True
            logger.info("Display initialization complete")

        except Exception as e:
            logger.error(f"Display initialization failed: {e}")
            raise

    def _configure_rotation(self):
        """Configure display rotation (0, 90, 180, 270 degrees)."""
        # Simplified rotation setup - actual implementation depends on GC9A01 specific registers
        # This is a placeholder that may need adjustment based on your specific display variant
        logger.debug(f"Configuring rotation: {self.rotation} degrees")

    def set_address_window(self, x0: int, y0: int, x1: int, y1: int):
        """Set the RAM address window for pixel writing.

        Args:
            x0: Start column address (0-239)
            y0: Start row address (0-239)
            x1: End column address (0-239)
            y1: End row address (0-239)
        """
        # Set column address window
        self._write_command(self.CMD_COLUMN_ADDR)
        # Most GC9A01 I2C implementations expect 16-bit addresses (big-endian)
        col_data = struct.pack('>HH', x0, x1)
        self._write_data(col_data)

        # Set row address window
        self._write_command(self.CMD_ROW_ADDR)
        row_data = struct.pack('>HH', y0, y1)
        self._write_data(row_data)

        logger.debug(f"Address window set: X({x0},{x1}) Y({y0},{y1})")

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
        if self.initialized:
            self._configure_rotation()

        logger.info(f"Display rotation set to {rotation_angle}°")
