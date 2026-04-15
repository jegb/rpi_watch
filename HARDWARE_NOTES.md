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

### SPI Pin Configuration (7PIN variant)
```
Pin 1 (GND)   → Ground
Pin 2 (VCC)   → 3.3V or 5V
Pin 3 (CLK)   → GPIO 11 (SCLK/Clock)
Pin 4 (MOSI)  → GPIO 10 (MOSI/Data)
Pin 5 (DC)    → GPIO 24 (Data/Command)
Pin 6 (RST)   → GPIO 25 (Reset)
Pin 7 (CS)    → GPIO 8 (Chip Select) - optional, can tie to GND
```

### SPI Pin Configuration (8PIN variant)
```
Adds Pin 8: GND (additional ground, same as Pin 1)
```

## Recommended SPI Driver

### Option 1: Adafruit Library (Easiest)
Use Adafruit's well-tested CircuitPython/Python libraries:
- **Library**: `adafruit-circuitpython-gc9a01`
- **Installation**: `pip install adafruit-circuitpython-gc9a01`
- **Advantage**: Production-grade, widely used, good documentation
- **Disadvantage**: May have more overhead than minimal implementation

### Option 2: Waveshare Driver
If you purchased from Waveshare, they provide Python libraries:
- **Library**: `waveshare-display` or similar
- **Installation**: Follow Waveshare's GitHub repository
- **Advantage**: Optimized for their specific board variant
- **Disadvantage**: May be specific to their version

### Option 3: Custom SPI Driver (Current Implementation - NEEDS UPDATE)
The current `gc9a01_i2c.py` is built for I2C, which is NOT your hardware. A custom SPI driver would need:
- **Library**: `RPi.GPIO` or `gpiozero` for GPIO control
- **SPI Library**: `spidev` for hardware SPI communication
- **Complexity**: High, requires detailed register manipulation

## Important: Update Required

The current project implementation in `src/rpi_watch/display/gc9a01_i2c.py` is designed for an **I2C variant** that you don't have.

### Recommended Action

**Switch to Adafruit Library** (easiest path):

1. Update `requirements.txt`:
   ```
   Pillow>=10.0.0
   paho-mqtt>=2.1.0
   adafruit-circuitpython-gc9a01>=1.4.3
   PyYAML>=6.0
   ```

2. Create new `src/rpi_watch/display/gc9a01_spi.py` that wraps Adafruit's driver
3. Update `src/rpi_watch/main.py` to use the SPI driver instead of I2C

### Alternative: Use Existing Projects

If you want to avoid rewriting, consider using:
- **Adafruit GC9A01 Examples**: https://github.com/adafruit/Adafruit_CircuitPython_GC9A01
- **Waveshare Examples**: https://github.com/waveshare/LCD_1.28_GC9A01

## Wiring Diagram

```
Raspberry Pi                    GC9A01 Display (SPI)
─────────────                  ──────────────────────
GPIO 2 (SDA)    ────────────   (Not used for SPI)
GPIO 3 (SCL)    ────────────   (Not used for SPI)

GPIO 11 (SCLK)  ────────────   CLK (Pin 3)
GPIO 10 (MOSI)  ────────────   MOSI (Pin 4)
GPIO 9 (MISO)   ────────────   (Not typically used)

GPIO 24 (any)   ────────────   DC (Pin 5) - Data/Command
GPIO 25 (any)   ────────────   RST (Pin 6) - Reset
GPIO 8 (any)    ────────────   CS (Pin 7) - Chip Select (optional)

3.3V            ────────────   VCC (Pin 2)
GND             ────────────   GND (Pin 1)
```

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
     spi_clock_pin: 11      # GPIO 11 (SCLK)
     spi_mosi_pin: 10       # GPIO 10 (MOSI)
     spi_dc_pin: 24         # GPIO 24 (Data/Command)
     spi_reset_pin: 25      # GPIO 25 (Reset)
     spi_cs_pin: 8          # GPIO 8 (Chip Select, optional)
     spi_bus: 0             # SPI bus number (0 for /dev/spidev0.0)
     spi_device: 0          # SPI device number
     spi_speed: 10000000    # Clock speed: 10 MHz
   ```

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

# Test GPIO pins
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(24, GPIO.OUT); print('GPIO OK')"
```

## Power Considerations

- **Current Draw**: 100-200 mA typical (display at full brightness)
- **Power Supply**: 5V 1A minimum recommended (3.3V via LDO regulator)
- **Voltage Levels**: RPi outputs 3.3V; display can accept 5V input (verify with datashee)
- **Level Shifting**: May need 3.3V↔5V converter if running from 5V supply

## Additional Resources

- **GC9A01 Datasheet**: [Request from supplier or search online]
- **Raspberry Pi GPIO**: https://www.raspberrypi.com/documentation/computers/gpio.html
- **SPI Reference**: https://en.wikipedia.org/wiki/Serial_Peripheral_Interface
- **Adafruit GC9A01**: https://github.com/adafruit/Adafruit_CircuitPython_GC9A01
