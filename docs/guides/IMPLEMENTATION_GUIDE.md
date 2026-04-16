# RPi Watch - Implementation Guide

## Important Discovery: Hardware Variant

Your GC9A01 display is the **SPI variant** (not I2C). This means we need to update the driver implementation.

### Current Status
- ✅ Project structure created
- ✅ MQTT integration implemented
- ✅ Rendering engine (PIL-based) implemented
- ✅ Configuration system in place
- ❌ Display driver needs SPI implementation (currently I2C)

## Implementation Roadmap

### Phase 1: SPI Driver Selection (Choose One Approach)

#### **Recommended: Adafruit Library**

**Pros:**
- Production-grade library
- Well-documented
- Active maintenance
- Handles all low-level details
- Wide community support

**Cons:**
- Additional dependency
- Slightly more overhead

**Steps:**
1. Install: `pip install adafruit-circuitpython-gc9a01`
2. Create wrapper in `src/rpi_watch/display/gc9a01_spi.py`
3. Implement similar API to current I2C driver
4. Test with `scripts/test_display_init.py`

**Estimated Effort**: 2-3 hours

#### Alternative: Custom SPI Implementation

**Pros:**
- Full control
- Minimal dependencies
- Optimized for your use case

**Cons:**
- More complex
- Requires GC9A01 datasheet
- More debugging required

**Requires:**
- `spidev` library for SPI communication
- `RPi.GPIO` for pin control
- Detailed register knowledge

**Estimated Effort**: 8-12 hours

### Phase 2: Update Driver Files

Replace current I2C driver with SPI version:

**File to modify**: `src/rpi_watch/display/gc9a01_spi.py`

Required methods (match current API):
```python
class GC9A01_SPI:
    def __init__(self, spi_bus=0, spi_device=0, dc_pin=24, reset_pin=25):
    def connect(self):
    def disconnect(self):
    def init_display(self):
    def display(self, pil_image):
    def write_pixels(self, rgb565_data):
    def reset(self):
    def set_rotation(self, angle):
```

### Phase 3: Update Configuration

Update `config/config.yaml`:
```yaml
display:
  # SPI pins (Raspberry Pi GPIO numbers)
  spi_clock_pin: 11
  spi_mosi_pin: 10
  spi_dc_pin: 24         # Data/Command
  spi_reset_pin: 25      # Reset
  spi_cs_pin: 8          # Chip Select (optional)
  spi_bus: 0
  spi_device: 0
  spi_speed: 10000000    # 10 MHz clock

  # Display settings
  width: 240
  height: 240
  rotation: 0
  refresh_rate_hz: 5     # Can be higher with SPI
```

### Phase 4: Update Main Application

Modify `src/rpi_watch/main.py`:
```python
from .display.gc9a01_spi import GC9A01_SPI  # Change from gc9a01_i2c

# In initialize_components():
self.display = GC9A01_SPI(
    spi_bus=display_config.get('spi_bus', 0),
    spi_device=display_config.get('spi_device', 0),
    dc_pin=display_config.get('spi_dc_pin', 24),
    reset_pin=display_config.get('spi_reset_pin', 25),
    cs_pin=display_config.get('spi_cs_pin', 8),
    spi_speed=display_config.get('spi_speed', 10000000)
)
```

### Phase 5: Testing

1. **Hardware Verification**:
   ```bash
   python3 scripts/test_spi_bus.py  # New test script needed
   ```

2. **Display Test**:
   ```bash
   python3 scripts/test_display_init.py
   ```

3. **Full Integration**:
   ```bash
   python3 -m rpi_watch.main
   ```

## Estimated Timeline

| Phase | Task | Effort | Status |
|-------|------|--------|--------|
| 1 | SPI Driver Selection | 1 hour | ✅ Done |
| 2 | Implement SPI Driver | 2-12 hours | ⏳ Pending |
| 3 | Update Configuration | 1 hour | ⏳ Pending |
| 4 | Update Main App | 1 hour | ⏳ Pending |
| 5 | Testing & Debugging | 2-4 hours | ⏳ Pending |

**Total Estimated Effort**: 7-19 hours (depending on driver choice)

## Quick Start (After Implementation)

```bash
# Clone/navigate to project
cd ~/rpi_watch

# Install dependencies
pip install -r requirements.txt

# Update configuration (if needed)
nano config/config.yaml

# Run application
python3 -m rpi_watch.main
```

## File Structure Summary

```
rpi_watch/
├── config/
│   ├── config.yaml                      # Main configuration
│   └── config.sps_monitor_examples.yaml # Example configs
│
├── src/rpi_watch/
│   ├── display/
│   │   ├── gc9a01_i2c.py               # ❌ DEPRECATED - I2C only
│   │   ├── gc9a01_spi.py               # ✅ TODO - Implement SPI
│   │   └── renderer.py                 # ✅ Ready
│   │
│   ├── mqtt/
│   │   └── subscriber.py               # ✅ Ready
│   │
│   ├── metrics/
│   │   └── metric_store.py             # ✅ Ready
│   │
│   ├── utils/
│   │   └── logging_config.py           # ✅ Ready
│   │
│   └── main.py                          # ⏳ Needs driver import update
│
├── scripts/
│   ├── test_i2c_bus.py                 # ❌ Not applicable for SPI
│   ├── test_display_init.py            # ⏳ Should work after SPI impl.
│   └── test_spi_bus.py                 # TODO - Create SPI version
│
└── tests/
    ├── test_renderer.py                # ✅ Ready
    └── test_metric_store.py            # ✅ Ready
```

## Known Working Components

These components are ready and don't need changes:

✅ **Rendering Engine** (`display/renderer.py`)
- PIL image generation
- Circular masking
- RGB565 conversion
- Font handling

✅ **MQTT Client** (`mqtt/subscriber.py`)
- Connection management
- JSON field extraction
- Thread-safe updates
- Error handling

✅ **Metric Storage** (`metrics/metric_store.py`)
- Thread-safe value storage
- Timestamp tracking
- Age calculation

✅ **Configuration System** (`config/config.yaml`)
- YAML-based configuration
- SPS Monitor integration ready
- Metric field selection

## Components Needing Updates

⏳ **SPI Driver** (`display/gc9a01_spi.py`)
- Need to create SPI implementation
- Use Adafruit library (recommended) or custom

⏳ **Test Scripts**
- `test_i2c_bus.py` → Not applicable for SPI
- `test_spi_bus.py` → Create new
- `test_display_init.py` → Update to use SPI driver

⏳ **Main Application** (`main.py`)
- Update imports: `gc9a01_i2c` → `gc9a01_spi`
- Update pin configuration
- Update initialization parameters

## Development Approach

### Option 1: Use Adafruit Library (Faster)
1. Install adafruit-circuitpython-gc9a01
2. Wrapper it in `gc9a01_spi.py`
3. Test
4. Done in 2-3 hours

### Option 2: Build Custom Driver (Educational)
1. Study GC9A01 datasheet
2. Implement SPI communication
3. Implement register initialization
4. Test
5. Takes 8-12 hours but gives full control

### Recommendation
Use **Option 1 (Adafruit)** because:
- Faster to implement
- Production-ready code
- Well-tested
- Less room for error
- Still allows full customization through wrapper

## Next Steps

1. **Choose SPI driver approach** (Adafruit recommended)
2. **Create `gc9a01_spi.py`** with chosen driver
3. **Update `main.py`** to use new driver
4. **Update configuration** for SPI pins
5. **Test** with `test_display_init.py`
6. **Run main application** with SPS Monitor

## Resources

- **Adafruit GC9A01**: https://github.com/adafruit/Adafruit_CircuitPython_GC9A01
- **GC9A01 Datasheet**: [Get from supplier or search online]
- **RPi GPIO Guide**: https://www.raspberrypi.com/documentation/computers/gpio.html
- **SPI Tutorial**: https://en.wikipedia.org/wiki/Serial_Peripheral_Interface

## Questions?

Refer to:
1. [HARDWARE_NOTES.md](../reference/HARDWARE_NOTES.md) - Hardware specifications and pin layout
2. [INTEGRATION_SPS_MONITOR.md](INTEGRATION_SPS_MONITOR.md) - SPS Monitor integration
3. [README.md](../../README.md) - General setup instructions
4. [ARCHITECTURE.md](../reference/ARCHITECTURE.md) - System design details
