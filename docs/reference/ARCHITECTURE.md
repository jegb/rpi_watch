# RPi Watch - Architecture & Design

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 MQTT Broker (Network)                       │
│              (e.g., Mosquitto on 192.168.x.x)               │
└────────────────────────▲─────────────────────────────────────┘
                         │
                    MQTT Protocol
                   (port 1883, TLS)
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                   Raspberry Pi                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              RPi Watch Application                     │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │          main.py (Event Loop)                    │  │  │
│  │  │  - Initializes all components                    │  │  │
│  │  │  - Runs 2-4 Hz display refresh loop              │  │  │
│  │  │  - Coordinates between MQTT and Display          │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │           ▲              ▲                ▲             │  │
│  │           │              │                │             │  │
│  │  ┌────────┴──┐  ┌────────┴─────┐  ┌──────┴───────┐    │  │
│  │  │   MQTT    │  │   Metrics    │  │   Display    │    │  │
│  │  │ Subscriber│  │    Store     │  │   Renderer   │    │  │
│  │  │           │  │              │  │              │    │  │
│  │  └──────┬────┘  └──────┬───────┘  └──────┬───────┘    │  │
│  │         │              │                  │             │  │
│  │         │         ┌─────▼────────────┐    │             │  │
│  │         │         │ MetricStore      │    │             │  │
│  │         │         │ Thread-Safe      │    │             │  │
│  │         │         │ Value Storage    │    │             │  │
│  │         │         └──────┬───────────┘    │             │  │
│  │         │                │                │             │  │
│  │         └────────────────┼────────────────┘             │  │
│  │                          │                              │  │
│  │         (PIL Image)       │    (RGB565 Bytes)           │  │
│  │                          ▼                              │  │
│  │                   ┌─────────────────┐                   │  │
│  │                   │  GC9A01_I2C     │                   │  │
│  │                   │  I2C Driver     │                   │  │
│  │                   └────────┬────────┘                   │  │
│  └────────────────────────────┼────────────────────────────┘  │
│                               │                                │
│                          I2C Protocol                          │
│                    (GPIO 2=SDA, GPIO 3=SCL)                   │
│                                │                                │
└────────────────────────────────┼────────────────────────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │  GC9A01 Display (I2C)     │
                    │  240x240 Circular Display │
                    │  16-bit RGB565 Color      │
                    └───────────────────────────┘
```

## Module Architecture

### 1. **main.py** - Application Controller
- Entry point and event loop orchestrator
- Configuration loading (YAML)
- Component initialization and lifecycle management
- Signal handling for graceful shutdown
- Main display refresh loop (configurable Hz)

**Key Methods:**
- `initialize_components()` - Creates display, renderer, MQTT client
- `run()` - Main event loop: poll metric → render → display
- `cleanup()` - Graceful shutdown

### 2. **display/gc9a01_i2c.py** - I2C Display Driver
Custom implementation for rare I2C variant of GC9A01.

**Responsibilities:**
- Low-level I2C communication via SMBus
- GC9A01 register initialization sequence
- Power-on sequence and reset handling
- RAM address window control
- Pixel data transmission in batches (SMBus block size ~32 bytes)
- RGB565 pixel format conversion

**Key Methods:**
- `connect()` / `disconnect()` - I2C bus management
- `init_display()` - Power-on and configuration sequence
- `write_pixels()` - Send pixel data to display
- `display()` - High-level API: PIL Image → I2C transmission
- `_convert_to_rgb565()` - PIL to RGB565 format conversion

**Performance Notes:**
- I2C speed: 100 kHz (standard), potentially 400 kHz
- Frame transmission: ~180 KB pixel data at 100 kHz ≈ 1.4 seconds per full frame
- Optimized with batched writes to reduce overhead

### 3. **display/renderer.py** - Graphics Renderer
PIL-based image rendering with circular masking.

**Responsibilities:**
- Convert numeric metrics to PIL Image objects
- Apply circular mask for round 240x240 display
- Center text with configurable font and size
- RGB color support (text and background)

**Key Methods:**
- `render_metric()` - Metric value → PIL Image
- `apply_circular_mask()` - Apply circular mask to image
- `render_and_mask()` - Combined render + mask operation
- `_create_circular_mask()` - Pre-computed mask (efficiency)
- `_load_font()` - Font loading with fallbacks

**Features:**
- Configurable decimal places
- Optional unit labels (°C, W, V, etc.)
- Custom text/background colors
- Pre-computed circular mask (reused for every frame)

### 4. **mqtt/subscriber.py** - MQTT Client
Non-blocking MQTT subscriber with callback architecture.

**Responsibilities:**
- Connect to MQTT broker
- Subscribe to configured topic
- Parse incoming metric payloads (numeric or JSON)
- Update MetricStore thread-safely
- Handle connection failures and reconnection

**Key Methods:**
- `start()` - Start background listener (non-blocking)
- `stop()` - Graceful shutdown
- `get_latest_metric()` - Retrieve current metric value
- `is_connected()` - Check broker connection status
- `_on_message()` - Callback for incoming messages

**Message Formats Supported:**
- Raw numeric: `23.5`
- JSON with value field: `{"value": 23.5}`
- JSON with multiple fields: `{"temp": 23.5, "humidity": 45}` (uses first numeric)

### 5. **metrics/metric_store.py** - Thread-Safe Storage
Thread-safe storage for metric values with timestamp tracking.

**Responsibilities:**
- Store latest metric value
- Timestamp management
- Thread synchronization (RLock)

**Key Methods:**
- `update(value, timestamp)` - Update metric
- `get_latest()` - Get current value
- `get_with_timestamp()` - Get value + timestamp
- `get_age_seconds()` - Age of metric in seconds
- `has_value()` - Check if value exists
- `reset()` - Clear stored value

**Thread Safety:**
- All methods protected by RLock
- Safe for concurrent MQTT updates + display reads
- No blocking operations in critical sections

### 6. **utils/logging_config.py** - Logging Setup
Centralized logging configuration.

**Features:**
- Console output to stderr
- Optional file logging
- Configurable log levels
- Formatted timestamps

## Data Flow

### Startup Sequence
1. Load YAML configuration from `config/config.yaml`
2. Initialize logging
3. Create MetricStore (empty initially)
4. Create GC9A01_I2C display driver and connect
5. Call `init_display()` for power-on sequence
6. Create MetricRenderer with font/colors
7. Create MQTTSubscriber (linked to MetricStore)
8. Call `mqtt_subscriber.start()` (non-blocking, background thread)
9. Enter main event loop

### Runtime Event Loop
```
while running:
    ┌─────────────────────────────┐
    │ Get current metric from     │
    │ MetricStore.get_latest()    │
    └──────────────┬──────────────┘
                   │
         ┌─────────▼──────────┐
         │ If value changed?  │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │ Render metric to   │
         │ PIL Image with     │
         │ circular mask      │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │ Convert to         │
         │ RGB565 bytes       │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │ Send via I2C to    │
         │ display            │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │ Sleep for frame    │
         │ period (e.g., 500ms│
         │ for 2 Hz)          │
         └────────────────────┘
```

### Background MQTT Thread
```
MQTTSubscriber.loop_start()
    │
    └─► paho.mqtt.client.loop() (background thread)
            │
            └─► Listens for messages on subscribed topic
                    │
                    └─► On message arrive:
                        1. Parse payload (numeric or JSON)
                        2. Call metric_store.update(value)
                        3. Return (loop continues)
```

## I2C Communication Protocol

### Display Command Format
```
┌─────────────────────┐
│ I2C Frame Structure  │
├─────────────────────┤
│ Slave Address       │ 0x3C or 0x3D (7-bit)
│ Register Address    │ 0x00 (command) or 0x01 (data)
│ Data Bytes          │ 1-32 bytes (SMBus limit)
└─────────────────────┘
```

### Initialization Sequence
1. Reset command (0x01)
2. Wait 150ms
3. Sleep Out command (0x11)
4. Wait 120ms
5. Set Pixel Format (0x3A, 0x55 for RGB565)
6. Set Gamma Curve (0x26)
7. Display ON (0x29)
8. Wait 120ms
9. Set Brightness (0x51, 0xFF)

### Pixel Data Transmission
1. Set Column Address (0x2A, X0:X1)
2. Set Row Address (0x2B, Y0:Y1)
3. Write RAM command (0x2C)
4. Send pixel data (RGB565 format):
   - 240 × 240 pixels × 2 bytes/pixel = 115,200 bytes
   - Sent in 32-byte chunks via I2C

## Configuration Schema

```yaml
display:
  i2c_address: 0x3C              # Device address
  i2c_bus: 1                      # RPi I2C bus
  width: 240                      # Display width
  height: 240                     # Display height
  rotation: 0                     # Rotation degrees
  refresh_rate_hz: 2              # Display refresh frequency

mqtt:
  broker_host: "192.168.1.100"   # Broker IP/hostname
  broker_port: 1883               # Broker port
  topic: "sensor/metric"          # Subscribe topic
  qos: 1                          # Quality of Service
  keepalive: 60                   # Keepalive seconds

metric_display:
  decimal_places: 1               # Decimal precision
  font_size: 80                   # Font size (points)
  font_path: "/path/to/font.ttf"  # TrueType font path
  unit_label: "°C"                # Optional unit
  text_color: [255, 255, 255]     # RGB text
  background_color: [0, 0, 0]     # RGB background

logging:
  level: "INFO"                   # Log level
  log_file: "/path/to/logfile"    # Optional file
```

## Error Handling Strategy

### I2C Communication Errors
- Logged but application continues
- Re-attempt on next display update
- User sees last valid metric

### MQTT Connection Errors
- Automatic reconnection by paho-mqtt
- Metric display shows last received value
- No blocking on connection failures

### Display Initialization Errors
- Critical: raises exception, aborts startup
- Prevents running with uninitialized display

### Thread Safety Errors
- MetricStore uses RLock (prevents deadlocks)
- All public methods thread-safe
- No recursive locking required

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| I2C Bus Speed | 100 kHz | Can be 400 kHz on newer RPi |
| Frame Buffer Size | 180 KB | 240×240 × 2 bytes RGB565 |
| Full Frame TX Time | ~1.4s | At 100 kHz |
| Display Refresh Rate | 2 Hz | Configurable, 0.5s per frame |
| MQTT Latency | <100ms | Network dependent |
| Render Time | <50ms | PIL operations on CPU |
| Memory Usage | ~50-100 MB | Python + dependencies |
| CPU Usage | <5% | Idle, 10-20% during refresh |

## Future Enhancements

1. **SPI Display Support** - Add driver for SPI GC9A01 variant
2. **Multiple Metrics** - Dashboard with 2-4 metrics
3. **Animation Transitions** - Smooth value transitions
4. **Web Dashboard** - Remote monitoring/configuration
5. **Bluetooth Input** - Metric source from BLE devices
6. **Custom Fonts** - Runtime font selection
7. **Brightness Control** - Automatic/manual brightness
8. **Sensor Integration** - Direct sensor interfaces (DHT, etc.)

## Testing Strategy

### Unit Tests
- `test_metric_store.py` - Thread safety, value handling
- `test_renderer.py` - Image rendering, circular masking

### Integration Tests
- `test_i2c_bus.py` - I2C bus detection and communication
- `test_display_init.py` - Full display initialization and rendering

### Hardware Tests
- Manual verification: I2C address detection
- Visual inspection: Display output correctness
- MQTT: Manual topic publishing and value updates

## Deployment Notes

1. **Single Metric Display** - Designed for one metric per display
2. **Always-On Design** - Intended for 24/7 operation (consider thermal)
3. **Network Dependent** - Requires functioning MQTT broker
4. **Graceful Degradation** - Works without metrics (shows "...")
5. **Log Rotation** - Implement externally (logrotate, etc.)
6. **Power Management** - Display auto-brightness not implemented (consider adding)
