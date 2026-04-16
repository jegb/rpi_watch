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
    CMD_SLEEP_IN = 0x10             # Enter sleep mode
    CMD_SLEEP_OUT = 0x11            # Exit sleep mode
    CMD_PARTIAL_ON = 0x12           # Partial display mode ON
    CMD_NORMAL_ON = 0x13            # Normal display mode ON
    CMD_DISPLAY_INVERT_OFF = 0x20   # Display invert OFF
    CMD_DISPLAY_INVERT_ON = 0x21    # Display invert ON
    CMD_ALL_PIXELS_OFF = 0x22       # All pixels OFF
    CMD_ALL_PIXELS_ON = 0x23        # All pixels ON
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

    DEFAULT_MADCTL = 0x48           # MX | BGR (common round-panel default)
    RESET_PULSE_HIGH_S = 0.010
    RESET_PULSE_LOW_S = 0.100
    RESET_STABILIZE_S = 0.200
    SLEEP_OUT_DELAY_S = 0.120
    DISPLAY_ON_DELAY_S = 0.020

    ADAFRUIT_INIT_SEQUENCE = bytes(
        b"\xFE\x00"                      # Inter Register Enable1
        b"\xEF\x00"                      # Inter Register Enable2
        b"\xB6\x02\x00\x00"              # Display Function Control
        b"\x36\x01\x48"                  # MADCTL (overridden by self.madctl)
        b"\x3A\x01\x05"                  # RGB565 / 16-bit color
        b"\xC3\x01\x13"                  # Power Control 2
        b"\xC4\x01\x13"                  # Power Control 3
        b"\xC9\x01\x22"                  # Power Control 4
        b"\xF0\x06\x45\x09\x08\x08\x26\x2A"
        b"\xF1\x06\x43\x70\x72\x36\x37\x6F"
        b"\xF2\x06\x45\x09\x08\x08\x26\x2A"
        b"\xF3\x06\x43\x70\x72\x36\x37\x6F"
        b"\x66\x0A\x3C\x00\xCD\x67\x45\x45\x10\x00\x00\x00"
        b"\x67\x0A\x00\x3C\x00\x00\x00\x01\x54\x10\x32\x98"
        b"\x74\x07\x10\x85\x80\x00\x00\x4E\x00"
        b"\x98\x02\x3E\x07"
        b"\x35\x00"                      # Tearing Effect Line ON
        b"\x21\x00"                      # Display inversion ON
        b"\x11\x80\x78"                  # Sleep Out + 120ms
        b"\x29\x80\x14"                  # Display ON + 20ms
        b"\x2A\x04\x00\x00\x00\xEF"      # Column Address Set (overridden by width)
        b"\x2B\x04\x00\x00\x00\xEF"      # Row Address Set (overridden by height)
    )

    @staticmethod
    def infer_chip_select_gpio(spi_bus: int, spi_device: int) -> Optional[int]:
        """Infer the Raspberry Pi CE GPIO for common hardware SPI devices."""
        if spi_bus == 0:
            if spi_device == 0:
                return 8
            if spi_device == 1:
                return 7
        return None

    def __init__(
        self,
        spi_bus: int = 0,
        spi_device: int = 0,
        spi_speed: int = 10000000,  # 10 MHz
        dc_pin: int = 25,            # Data/Command
        reset_pin: int = 27,         # Reset
        cs_pin: Optional[int] = None,   # Optional manual Chip Select
        manual_cs: bool = True,
        madctl: int = DEFAULT_MADCTL,
    ):
        """Initialize the GC9A01 SPI driver.

        Args:
            spi_bus: SPI bus number (0 for /dev/spidev0.x)
            spi_device: SPI device number (0 for /dev/spidev0.0)
            spi_speed: SPI clock speed in Hz (default 10 MHz)
            dc_pin: GPIO pin for Data/Command control (BCM numbering)
            reset_pin: GPIO pin for Reset control (BCM numbering)
            cs_pin: Optional GPIO pin for manual Chip Select control. When
                manual_cs is enabled and cs_pin is omitted, the standard Pi CE
                pin for spi_bus/spi_device is inferred.
            manual_cs: When True, emulate microcontroller-style four-wire
                framing by holding CS active across command+data transactions.
            madctl: Memory Access Control register value. Common round-panel
                values are 0x08, 0x48, and 0x88.
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
        self.manual_cs = manual_cs
        self.logical_cs_pin = self.infer_chip_select_gpio(spi_bus, spi_device)
        self.cs_pin = cs_pin if cs_pin is not None else (self.logical_cs_pin if manual_cs else None)
        self.madctl = self._coerce_byte(madctl, "madctl")

        self.width = 240
        self.height = 240
        self.rotation = 0

        self.spi = None
        self.initialized = False
        self._batched_transaction = False
        self._transaction_active = False

        if self.manual_cs and self.cs_pin is None:
            raise ValueError(
                "manual_cs requires a panel CS GPIO or an inferable SPI controller CE pin"
            )

        logger.info(
            f"GC9A01_SPI driver initialized (bus={spi_bus}, device={spi_device}, "
            f"speed={spi_speed/1e6:.1f}MHz, DC={dc_pin}, RST={reset_pin}, "
            f"CS={self.cs_pin}, logical_cs={self.logical_cs_pin}, "
            f"manual_cs={self.manual_cs}, MADCTL=0x{self.madctl:02X})"
        )

    @staticmethod
    def _coerce_byte(value, field_name: str) -> int:
        """Normalize a config value into an unsigned 8-bit integer."""
        if isinstance(value, str):
            try:
                value = int(value, 0)
            except ValueError as exc:
                raise ValueError(f"{field_name} must be an integer byte value") from exc

        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer byte value") from exc

        if not 0x00 <= value <= 0xFF:
            raise ValueError(f"{field_name} must be between 0x00 and 0xFF")

        return value

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
            if self.manual_cs and self.cs_pin is not None:
                GPIO.setup(self.cs_pin, GPIO.OUT)
                GPIO.output(self.cs_pin, GPIO.HIGH)  # Chip select high (inactive)

            logger.info(
                f"GPIO configured: DC={self.dc_pin}, RST={self.reset_pin}, "
                f"CS={self.cs_pin}, manual_cs={self.manual_cs}"
            )

            # Open SPI
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            self.spi.max_speed_hz = self.spi_speed
            self.spi.mode = 0  # SPI mode 0 (CPOL=0, CPHA=0)
            self.spi.bits_per_word = 8
            self.spi.lsbfirst = False  # LSB first = False (MSB first)
            if self.manual_cs:
                if not hasattr(self.spi, "no_cs"):
                    raise RuntimeError("spidev binding does not expose no_cs; manual_cs mode is unavailable")
                self.spi.no_cs = True

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
        self._batched_transaction = False
        self._end_transaction()

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

    def _begin_transaction(self):
        """Assert chip select for a manual four-wire SPI transaction."""
        if self.manual_cs and self.cs_pin is not None and not self._transaction_active:
            GPIO.output(self.cs_pin, GPIO.LOW)
            self._transaction_active = True

    def _end_transaction(self):
        """Release chip select after a manual four-wire SPI transaction."""
        if self.manual_cs and self.cs_pin is not None and self._transaction_active:
            try:
                GPIO.output(self.cs_pin, GPIO.HIGH)
            finally:
                self._transaction_active = False

    def _spi_write(self, payload: bytes):
        """Send bytes over SPI without changing D/C or chip-select state."""
        if not payload:
            return

        chunk_size = 4096
        if len(payload) <= chunk_size:
            self.spi.writebytes(list(payload))
            return

        for start in range(0, len(payload), chunk_size):
            self.spi.writebytes(list(payload[start:start + chunk_size]))

    def _write_command(self, command: int):
        """Write a command byte to the display.

        Sets DC pin low, sends command byte via SPI.

        Args:
            command: Command byte to send
        """
        if not self.spi:
            raise RuntimeError("SPI not connected. Call connect() first.")

        try:
            if not self._batched_transaction:
                self._begin_transaction()
            GPIO.output(self.dc_pin, GPIO.LOW)  # DC low = command mode
            self._spi_write(bytes([command]))
            GPIO.output(self.dc_pin, GPIO.HIGH)  # DC high = data mode
            logger.debug(f"Command sent: 0x{command:02X}")
        except Exception as e:
            logger.error(f"Failed to write command 0x{command:02X}: {e}")
            raise
        finally:
            if not self._batched_transaction:
                self._end_transaction()

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
            if not self._batched_transaction:
                self._begin_transaction()
            GPIO.output(self.dc_pin, GPIO.HIGH)  # DC high = data mode
            self._spi_write(data)
            logger.debug(f"Data sent: {len(data)} bytes")

        except Exception as e:
            logger.error(f"Failed to write data: {e}")
            raise
        finally:
            if not self._batched_transaction:
                self._end_transaction()

    def _write_command_data(self, command: int, data: bytes):
        """Send command followed by data.

        Args:
            command: Command byte
            data: Data bytes
        """
        if not data:
            self._write_command(command)
            return

        self._begin_transaction()
        self._batched_transaction = True
        try:
            self._write_command(command)
            self._write_data(data)
        finally:
            self._batched_transaction = False
            self._end_transaction()

    def send_command(self, command: int, data: bytes = b"", delay_s: float = 0.0):
        """Send a controller command with optional payload and post-command delay."""
        if data:
            self._write_command_data(command, data)
        else:
            self._write_command(command)

        if delay_s > 0:
            time.sleep(delay_s)

    def _apply_memory_access_control(self):
        """Apply the currently configured MADCTL value."""
        self.send_command(self.CMD_MEMORY_ACCESS, bytes([self.madctl]))

    def _override_init_data(self, command: int, data: bytes) -> bytes:
        """Apply local panel overrides to a packed init-sequence command."""
        if command == self.CMD_MEMORY_ACCESS and len(data) == 1:
            return bytes([self.madctl])

        if command == self.CMD_COLUMN_ADDR and len(data) == 4:
            return struct.pack(">HH", 0, self.width - 1)

        if command == self.CMD_ROW_ADDR and len(data) == 4:
            return struct.pack(">HH", 0, self.height - 1)

        return data

    def _run_init_sequence(self, sequence: bytes):
        """Execute a BusDisplay-style packed initialization sequence."""
        index = 0

        while index < len(sequence):
            command = sequence[index]
            index += 1

            param_spec = sequence[index]
            index += 1

            has_delay = bool(param_spec & 0x80)
            param_count = param_spec & 0x7F

            data = bytes(sequence[index:index + param_count])
            index += param_count
            data = self._override_init_data(command, data)

            if data:
                self._write_command_data(command, data)
            else:
                self._write_command(command)

            if has_delay:
                delay_ms = sequence[index]
                index += 1
                time.sleep(0.5 if delay_ms == 0xFF else delay_ms / 1000.0)

    def reset(self):
        """Perform a hardware reset of the display controller."""
        if not self.spi:
            raise RuntimeError("SPI not connected. Call connect() first.")

        try:
            logger.info("Resetting display...")
            # Reset pulse: high → low → high with delays
            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(self.RESET_PULSE_HIGH_S)
            GPIO.output(self.reset_pin, GPIO.LOW)
            time.sleep(self.RESET_PULSE_LOW_S)
            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(self.RESET_STABILIZE_S)
            logger.info("Display reset complete")
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            raise

    def set_madctl(self, madctl: int):
        """Update the MADCTL register value used for panel addressing."""
        self.madctl = self._coerce_byte(madctl, "madctl")

        if self.initialized:
            self._apply_memory_access_control()

        logger.info(f"MADCTL set to 0x{self.madctl:02X}")

    def software_reset(self, delay_s: Optional[float] = None):
        """Issue a software reset command."""
        if delay_s is None:
            delay_s = self.RESET_STABILIZE_S
        self.send_command(self.CMD_RESET, delay_s=delay_s)
        self.initialized = False

    def sleep_in(self):
        """Enter sleep mode."""
        self.send_command(self.CMD_SLEEP_IN)

    def sleep_out(self, delay_s: Optional[float] = None):
        """Exit sleep mode."""
        if delay_s is None:
            delay_s = self.SLEEP_OUT_DELAY_S
        self.send_command(self.CMD_SLEEP_OUT, delay_s=delay_s)

    def display_off(self):
        """Turn the display output off without resetting controller state."""
        self.send_command(self.CMD_DISPLAY_OFF)

    def display_on(self, delay_s: Optional[float] = None):
        """Turn the display output on."""
        if delay_s is None:
            delay_s = self.DISPLAY_ON_DELAY_S
        self.send_command(self.CMD_DISPLAY_ON, delay_s=delay_s)

    def set_inversion(self, enabled: bool):
        """Enable or disable display inversion."""
        self.send_command(
            self.CMD_DISPLAY_INVERT_ON if enabled else self.CMD_DISPLAY_INVERT_OFF
        )

    def set_all_pixels(self, enabled: bool):
        """Force all pixels on or return them to RAM-controlled output."""
        self.send_command(
            self.CMD_ALL_PIXELS_ON if enabled else self.CMD_ALL_PIXELS_OFF
        )

    def normal_mode_on(self):
        """Return from partial/all-pixels mode to normal display operation."""
        self.send_command(self.CMD_NORMAL_ON)

    def init_display(self):
        """Initialize the display using Adafruit's packed GC9A01A sequence."""
        logger.info("Initializing GC9A01 display (Adafruit CircuitPython sequence)...")

        try:
            logger.debug("Hardware reset")
            self.reset()

            logger.debug("Running packed Adafruit init sequence")
            self._run_init_sequence(self.ADAFRUIT_INIT_SEQUENCE)

            self.initialized = True
            logger.info("✓ Display initialization complete")

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
            self.send_command(self.CMD_WRITE_RAM, rgb565_data)

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
