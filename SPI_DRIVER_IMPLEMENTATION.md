# SPI Driver Implementation - Step-by-Step Guide

**Status**: SPI Driver Fully Implemented with Adafruit Sequence ✅
**Hardware**: GC9A01 1.28" Round Display (SPI Variant - 8PIN)
**Date**: April 15, 2026
**Reference**: Based on Adafruit_GC9A01A (https://github.com/adafruit/Adafruit_GC9A01A)

## What Has Been Implemented

### 1. Core SPI Driver (`src/rpi_watch/display/gc9a01_spi.py`)

✅ **Complete SPI Communication Layer**
- Hardware SPI via `spidev` library
- GPIO control via `RPi.GPIO` library
- Command/Data mode switching (DC pin)
- Reset sequence handling
- Display initialization with power-on sequence

✅ **Display Operations**
- Address window configuration
- Pixel data transmission
- RGB565 color format conversion
- Full frame buffer management

✅ **Built-in Testing Methods**
- `test_spi_communication()` - Test basic SPI with reset
- `test_address_setup()` - Test address window configuration
- `test_payload_transfer()` - Test data transmission speed
- `test_full_frame_transfer()` - Test complete frame refresh

### 2. Comprehensive Test Suite (`scripts/test_spi_bus.py`)

✅ **Step-by-Step Hardware Verification**
1. **SPI Bus Detection** - Check `/dev/spidev0.0` availability
2. **GPIO Configuration** - Verify pin setup (DC, RST, CS)
3. **SPI Connection** - Open SPI bus and configure speed
4. **Display Reset** - Test hardware reset sequence
5. **Address Window** - Verify RAM address setup
6. **Payload Transfer** - Test 1KB, 32KB data transfers
7. **Full Frame Transfer** - Test 240x240 RGB565 (115.2 KB)

Each test provides detailed feedback on success/failure.

### 3. UI Component Library (`src/rpi_watch/display/components.py`)

✅ **Text Rendering Engine**
- Multiple font sizes: XL (96pt), Large (64pt), Normal (48pt), Small (32pt), Tiny (20pt)
- Text alignment: Left, Center, Right
- Multi-line layouts with different sizes:
  - Main text (XL)
  - Subtitle (Normal)
  - Detail (Small)
- Custom colors and backgrounds
- Font fallback system

✅ **Circular Gauge Component**
- Single-ring gauge with arc indicator
- Needle pointer showing current value
- Configurable min/max range
- Multi-ring gauge for multiple metrics
- Custom colors for each ring
- Center value display

✅ **Progress Indicators**
- Linear progress bar with percentage
- Circular progress indicator
- Customizable colors and sizes
- Optional percentage display

### 4. Component Testing (`scripts/test_components.py`)

✅ **Comprehensive Component Tests**
- Text rendering at all sizes
- Multi-line text layouts
- Single-ring gauges
- Multi-ring gauges (2-4 rings)
- Linear progress bars
- Circular progress indicators
- Combined layout blending
- Color variations (7 color schemes)

## PIN CONFIGURATION (8PIN Variant - Current Hardware)

```
GC9A01 Display (8PIN)         Raspberry Pi GPIO
──────────────────────────────────────────────────

Pin 1: GND        ───────────  GND (Pin 6, 9, 14, 20, 25, 30, 34, 39)
Pin 2: VCC        ───────────  3.3V (Pin 1 or 17)
Pin 3: CLK        ───────────  GPIO 11 (SCLK) - Hardware SPI Clock
Pin 4: MOSI       ───────────  GPIO 10 (MOSI) - Hardware SPI Data
Pin 5: RES        ───────────  GPIO 25 (Reset)
Pin 6: DC         ───────────  GPIO 24 (Data/Command)
Pin 7: CS         ───────────  GPIO 8 (Chip Select, optional - can tie to GND)
Pin 8: BLK        ───────────  3.3V (Backlight - tie to 3.3V for full brightness)

Critical Notes:
- Pin 3 (CLK) & Pin 4 (MOSI) MUST use hardware SPI (GPIO 11 & 10 on RPi)
- Pin 5 (RES) & Pin 6 (DC) can use any GPIO pins (set in config.yaml)
- Pin 7 (CS) is optional - can be tied to GND if not used
- Pin 8 (BLK) can be PWM for brightness control, or tie to 3.3V
```

### Legacy 7PIN Variant (if applicable)
```
If you have an older 7-pin display:
Pin 1: GND        ───────────  GND
Pin 2: VCC        ───────────  3.3V
Pin 3: CLK        ───────────  GPIO 11 (SCLK)
Pin 4: MOSI       ───────────  GPIO 10 (MOSI)
Pin 5: DC         ───────────  GPIO 24 (Data/Command)
Pin 6: RST        ───────────  GPIO 25 (Reset)
Pin 7: CS         ───────────  GPIO 8 (Chip Select, optional)
```

## Display Initialization Sequence (Adafruit-Based)

The enhanced initialization sequence in `gc9a01_spi.py` follows Adafruit's proven GC9A01 approach:

### Step-by-Step Initialization

1. **Hardware Reset** - Reset pulse (high → low → high)
2. **Software Reset** - Clear internal state
3. **Exit Sleep Mode** - Wake up the display
4. **Set Pixel Format** - Configure RGB565 16-bit color mode
5. **Memory Access Control** - Set rotation/mirror settings
6. **Power Control** - Configure voltage regulators:
   - VRH (voltage regulator) = 0x14
   - BT (AVDD/GVDD) = 0xA2
   - Voltage follower = 0x02
7. **Gamma Curves** - Apply calibration curves for color accuracy:
   - Positive gamma (16 values)
   - Negative gamma (16 values)
8. **Normal Display Mode** - Set to normal operation
9. **Display ON** - Enable display output
10. **Brightness** - Set to maximum (0xFF)

### Timing Requirements

- Reset pulse: 50ms low, 150ms high
- Sleep out → Display on: 120ms each
- Total initialization: ~600ms

### Why This Sequence Works

The Adafruit sequence includes critical power control and gamma calibration steps that basic initialization sequences miss. This ensures:
- Proper voltage regulation for stable display
- Accurate color reproduction
- Reliable operation across different GC9A01 variants
- Compatibility with both 7PIN and 8PIN displays

## Configuration Files

### Main Configuration (`config/config.yaml`)

```yaml
display:
  # SPI hardware configuration
  spi_bus: 0                 # Hardware SPI bus 0
  spi_device: 0              # Device on bus 0
  spi_speed: 10000000        # 10 MHz (default safe speed)

  # GPIO pin configuration
  spi_dc_pin: 24             # Data/Command pin
  spi_reset_pin: 25          # Reset pin
  spi_cs_pin: 8              # Chip Select (optional)

  # Display settings
  width: 240
  height: 240
  refresh_rate_hz: 5         # Can achieve 5+ Hz with SPI
```

## Testing Procedure

### Phase 1: Basic Hardware Verification

**Step 1a: Check SPI Bus**
```bash
ls -la /dev/spidev0.*
# Should show: crw------- 1 root root /dev/spidev0.0
```

**Step 1b: Enable SPI (if needed)**
```bash
sudo raspi-config
# → Interfacing Options → SPI → Enable
sudo reboot
```

**Step 1c: Install Dependencies**
```bash
pip install spidev RPi.GPIO Pillow paho-mqtt PyYAML
```

### Phase 2: Run Comprehensive SPI Test Suite

```bash
cd ~/rpi_watch
python3 scripts/test_spi_bus.py
```

**Expected Output:**
```
======================================================================
RPi Watch - SPI Bus & Display Communication Test Suite
======================================================================

────────────────────────────────────────────────────────────────────
Test: SPI Bus Detection
────────────────────────────────────────────────────────────────────
Checking for SPI bus availability...
✓ spidev library available
✓ RPi.GPIO library available
✓ SPI device /dev/spidev0.0 accessible
  SPI Mode: 0
  Max Speed: 50000000
✅ PASSED: SPI Bus Detection

────────────────────────────────────────────────────────────────────
Test: GPIO Pin Configuration
────────────────────────────────────────────────────────────────────
Configuring GPIO pins...
  DC pin: GPIO 24
  RST pin: GPIO 25
  CS pin: GPIO 8
✓ GPIO pins configured successfully
✓ DC pin toggle successful
✓ RST pin toggle successful
✅ PASSED: GPIO Pin Configuration

────────────────────────────────────────────────────────────────────
Test: SPI Connection
────────────────────────────────────────────────────────────────────
Creating SPI display driver...
✓ Driver instance created
Connecting to SPI bus...
✓ SPI bus connected
✅ PASSED: SPI Connection

[... more tests ...]

======================================================================
TEST SUMMARY
======================================================================
Passed: 8/8
Failed: 0/8
  ✅ SPI Bus Detection
  ✅ GPIO Pin Configuration
  ✅ SPI Connection
  ✅ Display Reset Sequence
  ✅ Address Window Setup
  ✅ Payload Transfer (small)
  ✅ Payload Transfer (medium)
  ✅ Full Frame Transfer
======================================================================
```

### Phase 3: Test Component Rendering

```bash
python3 scripts/test_components.py
```

This creates test images showing:
- Text rendering at 5 different sizes
- Multi-line layouts
- Single and multi-ring gauges
- Progress bars and indicators
- Color variations

Images are saved to `/tmp/test_*.png`

### Phase 4: Run Main Application

```bash
# Make sure SPS Monitor is publishing to 192.168.0.214:1883
python3 -m rpi_watch.main
```

Expected output:
```
2026-04-15 13:45:00 - rpi_watch.main - INFO - Initializing RPi Watch application
2026-04-15 13:45:00 - rpi_watch.display.gc9a01_spi - INFO - GC9A01_SPI driver initialized
2026-04-15 13:45:00 - rpi_watch.display.gc9a01_spi - INFO - Connected to SPI bus 0.0 at 10.0MHz
2026-04-15 13:45:01 - rpi_watch.display.gc9a01_spi - INFO - Initializing GC9A01 display...
2026-04-15 13:45:01 - rpi_watch.display.gc9a01_spi - INFO - Display initialization complete
2026-04-15 13:45:02 - rpi_watch.mqtt.subscriber - INFO - Connected to MQTT broker: 192.168.0.214:1883
2026-04-15 13:45:02 - rpi_watch.mqtt.subscriber - INFO - Subscribed to topic: airquality/sensor
2026-04-15 13:45:03 - rpi_watch.main - INFO - Display updated (frame 1): 25.5
```

Display should show PM2.5 value updating in real-time.

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| SPI Clock Speed | 10 MHz | Default (can go to 40-50 MHz) |
| Data Rate | 1.25 MB/s | At 10 MHz clock |
| Frame Size | 115.2 KB | 240×240 × 2 bytes RGB565 |
| Full Frame TX Time | ~92 ms | At 10 MHz |
| Theoretical Max FPS | 10.9 | At 10 MHz |
| Practical FPS | 5-8 | With Python overhead |

**With 20 MHz SPI Speed:**
- Data Rate: 2.5 MB/s
- Full Frame Time: ~46 ms
- Practical FPS: 10-15

## Code Organization

```
src/rpi_watch/display/
├── __init__.py                  # Package exports (updated for SPI)
├── gc9a01_spi.py               # SPI driver (✅ NEW - fully implemented)
├── gc9a01_i2c.py               # I2C driver (deprecated reference)
├── renderer.py                 # PIL-based metric rendering
└── components.py               # Text, gauge, progress components (✅ NEW)

scripts/
├── test_spi_bus.py             # SPI communication testing (✅ NEW)
├── test_components.py          # Component rendering testing (✅ NEW)
├── test_display_init.py        # Display initialization (updated)
└── test_i2c_bus.py             # I2C testing (deprecated)
```

## Usage Examples

### Example 1: Display a Large Metric

```python
from rpi_watch.display import GC9A01_SPI, MetricRenderer

# Initialize display
display = GC9A01_SPI(dc_pin=24, reset_pin=25)
display.connect()
display.init_display()

# Render and display
renderer = MetricRenderer()
image = renderer.render_metric(23.5, decimal_places=1, unit_label="°C")
display.display(image)
```

### Example 2: Display with Gauge

```python
from rpi_watch.display import GC9A01_SPI, CircularGauge, TextRenderer

display = GC9A01_SPI()
display.connect()
display.init_display()

# Create gauge
gauge = CircularGauge()
image = gauge.render_gauge(
    value=75.0,
    min_value=0.0,
    max_value=100.0,
    gauge_color=(0, 255, 0)
)
display.display(image)
```

### Example 3: Multi-Line Text

```python
from rpi_watch.display import GC9A01_SPI, TextRenderer

display = GC9A01_SPI()
display.connect()
display.init_display()

text = TextRenderer()
image = text.render_multiline(
    main_text="23.5",
    sub_text="Temperature",
    detail_text="Living Room",
    main_color=(255, 100, 0)
)
display.display(image)
```

### Example 4: Multi-Ring Gauge

```python
from rpi_watch.display import GC9A01_SPI, CircularGauge

display = GC9A01_SPI()
display.connect()
display.init_display()

gauge = CircularGauge()
image = gauge.render_multi_ring_gauge(
    values=[25.0, 50.0, 75.0],  # 3 metrics
    min_value=0.0,
    max_value=100.0
)
display.display(image)
```

## Troubleshooting

### SPI Bus Not Found
```
Error: No such file or directory: '/dev/spidev0.0'
```
**Solution**: Run `sudo raspi-config` → Interfacing → SPI → Enable

### GPIO Permission Denied
```
Error: No permission to access /sys/class/gpio/gpio24
```
**Solution**: Run script with sudo or add user to gpio group:
```bash
sudo usermod -a -G gpio $USER
```

### Display Not Initializing
```
Error: Display initialization failed
```
**Solution**:
1. Check GPIO pins connected correctly
2. Verify power supply (3.3V + GND)
3. Check SPI speed is reasonable (10 MHz default)
4. Run test_spi_bus.py to debug

### Garbled Display Output
```
Display shows random pixels or freezes
```
**Solutions**:
1. Lower SPI speed: `spi_speed: 5000000` (5 MHz)
2. Add pull-up resistors (4.7kΩ) on DC/RST pins
3. Check cable length (keep short)
4. Verify stable power supply

## What's Next

After successful SPI driver implementation:

1. **Production Deployment**
   - Test with real SPS Monitor data
   - Optimize refresh rate and colors
   - Deploy as systemd service

2. **Advanced Features**
   - Animation transitions
   - Touch/button controls
   - Multiple display modes
   - Data logging

3. **Performance Optimization**
   - Increase SPI speed to 20-40 MHz
   - Implement partial screen updates
   - Optimize frame buffer management

## Files Changed/Created

✅ **New Files**
- `src/rpi_watch/display/gc9a01_spi.py` - SPI driver
- `src/rpi_watch/display/components.py` - Text, gauge, progress components
- `scripts/test_spi_bus.py` - SPI communication testing
- `scripts/test_components.py` - Component rendering testing
- `SPI_DRIVER_IMPLEMENTATION.md` - This file

📝 **Modified Files**
- `src/rpi_watch/display/__init__.py` - Export SPI driver and components
- `src/rpi_watch/main.py` - Use SPI driver instead of I2C
- `config/config.yaml` - SPI pin configuration

💾 **Deprecated Files** (still in repo for reference)
- `src/rpi_watch/display/gc9a01_i2c.py` - I2C driver (for reference only)
- `scripts/test_i2c_bus.py` - I2C testing (not applicable to hardware)

## Summary

✅ **SPI Driver**: Fully implemented with complete command/data protocol
✅ **Testing**: Comprehensive test suite covering all communication layers
✅ **Components**: Text rendering, circular gauges, progress indicators
✅ **Configuration**: Pre-configured for SPS Monitor integration
✅ **Documentation**: Step-by-step testing guide with troubleshooting

**Status**: Ready for on-hardware testing and production deployment

**Next**: Run `python3 scripts/test_spi_bus.py` to verify hardware communication
