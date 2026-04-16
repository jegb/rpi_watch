# Hardware Configuration Notes

## Display Variant

**Actual Hardware**: GC9A01 1.28" Round TFT LCD - **SPI Variant**
- **Interface**: 7PIN or 8PIN SPI (NOT I2C)
- **Resolution**: 240×240 pixels
- **Color Depth**: 16-bit (65K colors)
- **Driver IC**: GC9A01

### Display Specifications
- **Display Size**: 1.28 inches diagonal
- **Shape**: Circular (240×240 round format)
- **Communication**: SPI (Serial Peripheral Interface)
- **Power**: 3.3V typical (5V tolerant with level shifter)
- **Data Format**: 16-bit RGB565 (5-bit R, 6-bit G, 5-bit B)

### SPI Pin Configuration (8PIN variant - Current Hardware)
```
Pin 1 (GND)   → Ground
Pin 2 (VCC)   → 5V (recommended) or 3.3V
Pin 3 (CLK)   → GPIO 12 (SCLK/Clock) - or GPIO 11 if using SPI0
Pin 4 (MOSI)  → GPIO 11 (MOSI/Data) - or GPIO 10 if using SPI0
Pin 5 (RES)   → GPIO 2 (Reset)
Pin 6 (DC)    → GPIO 4 (Data/Command)
Pin 7 (CS)    → GPIO 5 (Chip Select) - optional, can tie to GND
Pin 8 (BLK)   → 5V or 3.3V (Backlight/LED control - tie high for full brightness)
```

### SPI Pin Configuration (7PIN variant - Legacy)
```
If you have a 7-pin variant:
Pin 1 (GND)   → Ground
Pin 2 (VCC)   → 3.3V or 5V
Pin 3 (CLK)   → GPIO 11 (SCLK/Clock)
Pin 4 (MOSI)  → GPIO 10 (MOSI/Data)
Pin 5 (DC)    → GPIO 24 (Data/Command)
Pin 6 (RST)   → GPIO 25 (Reset)
Pin 7 (CS)    → GPIO 8 (Chip Select) - optional, can tie to GND
```

## SPI Driver Implementation

### Current Implementation: Custom SPI Driver ✅
The project uses a **custom SPI driver** (`src/rpi_watch/display/gc9a01_spi.py`) that is:
- **Based on**: Adafruit_GC9A01A reference implementation (https://github.com/adafruit/Adafruit_GC9A01A)
- **Implementation**: Pure Python with RPi.GPIO and spidev
- **Advantages**:
  - No external dependencies beyond spidev and RPi.GPIO
  - Direct hardware control for maximum performance
  - Proven Adafruit initialization sequence
  - Compatible with both 7PIN and 8PIN variants
  - No CircuitPython overhead
- **Requirements**: Only `spidev` and `RPi.GPIO` (no Adafruit package needed)

### Why Custom Implementation?

1. **Availability**: `adafruit-circuitpython-gc9a01` is not available on Raspberry Pi ARM
2. **Performance**: Direct SPI control via `spidev` is faster
3. **Simplicity**: Minimal dependencies (only `spidev` + `RPi.GPIO`)
4. **Proven**: Implementation follows Adafruit's tested initialization sequence

### Initialization Sequence

The custom driver includes the complete Adafruit GC9A01 initialization sequence:
1. Hardware reset
2. Software reset
3. Sleep mode exit
4. Pixel format configuration (RGB565)
5. Memory access control
6. Power control (VRH, BT, voltage follower)
7. Gamma curve calibration
8. Display mode configuration
9. Display enable
10. Brightness control

See [SPI_DRIVER_IMPLEMENTATION.md](../guides/SPI_DRIVER_IMPLEMENTATION.md) for
detailed step-by-step breakdown.

## Wiring Diagram

```
Raspberry Pi                    GC9A01 Display (SPI)
─────────────                  ──────────────────────
GPIO 12 (CLK)   ────────────   CLK (Pin 3)
GPIO 11 (MOSI)  ────────────   MOSI (Pin 4)
GPIO 9 (MISO)   ────────────   (Not typically used)

GPIO 4 (any)    ────────────   DC (Pin 6) - Data/Command
GPIO 2 (any)    ────────────   RES (Pin 5) - Reset
GPIO 5 (any)    ────────────   CS (Pin 7) - Chip Select (optional)

5V (VIN)        ────────────   VCC (Pin 2)
GND             ────────────   GND (Pin 1)
5V or 3.3V      ────────────   BLK (Pin 8) - Backlight/LED
```

**Note**: If you're using SPI0 instead of SPI1, use GPIO 11 (CLK) and GPIO 10 (MOSI).

## Performance Characteristics (SPI)

| Metric | Value | Notes |
|--------|-------|-------|
| Clock Speed | 10-20 MHz | Typical safe speed for RPi |
| Data Rate | 1.25-2.5 MB/s | 10-20 MHz clock |
| Frame Size | 115,200 bytes | 240×240 × 2 bytes RGB565 |
| Full Frame TX | 46-92 ms | Significantly faster than I2C! |
| Theoretical Refresh | 10-20 Hz | Can achieve higher frame rates |
| Practical Refresh | 5-10 Hz | With Python overhead |

**Advantage**: SPI is much faster than I2C, enabling smoother animations and faster updates.

## Configuration Changes Needed

1. **Display pins** - Update `config/config.yaml`:
   ```yaml
   display:
     spi_bus: 0             # SPI bus number (0 for /dev/spidev0.0, 1 for /dev/spidev1.0)
     spi_device: 0          # SPI device number
     spi_speed: 10000000    # Clock speed: 10 MHz
     spi_dc_pin: 4          # GPIO 4 (Data/Command)
     spi_reset_pin: 2       # GPIO 2 (Reset)
     spi_cs_pin: 5          # GPIO 5 (Chip Select, optional)
   ```
   **Note**: Hardware SPI pins (CLK/MOSI) are automatically handled by the kernel.
   - If using SPI1 (GPIO 12/11): Update `spi_bus: 1`
   - If using SPI0 (GPIO 11/10): Keep `spi_bus: 0`

2. **Driver selection** - Choose between:
   - Adafruit library (recommended)
   - Waveshare library
   - Custom implementation

## Next Steps

1. Test SPI communication with Adafruit example code
2. Update `gc9a01_spi.py` to wrap SPI driver
3. Test with `scripts/test_display_init.py`
4. Run main application: `python3 -m rpi_watch.main`

## Debugging SPI Connection

```bash
# List SPI devices
ls -la /dev/spidev*

# Test with Python
python3 -c "import spidev; spi = spidev.SpiDev(); spi.open(0, 0); print('SPI OK')"

# Test GPIO pins (DC, RST, CS)
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup([4, 2, 5], GPIO.OUT); print('GPIO OK')"
```

## Power Considerations

- **Vcc (Display Power)**: **5V recommended** (datasheet supports 3.3V–5.5V, 5V is more reliable)
- **BLK (Backlight)**: 5V or 3.3V (tie to positive rail for full brightness, or use PWM for variable brightness)
- **Current Draw**: 100-200 mA typical (display + backlight at full brightness)
- **Power Supply**: 5V 2A minimum recommended
- **Voltage Levels**: RPi outputs 3.3V; display accepts 3.3V–5.5V input
- **Level Shifting**: Not typically needed for this display variant (tolerates 3.3V GPIO signals)

## Additional Resources

- **GC9A01 Datasheet**: [Request from supplier or search online]
- **Raspberry Pi GPIO**: https://www.raspberrypi.com/documentation/computers/gpio.html
- **SPI Reference**: https://en.wikipedia.org/wiki/Serial_Peripheral_Interface
- **Adafruit GC9A01**: https://github.com/adafruit/Adafruit_CircuitPython_GC9A01
