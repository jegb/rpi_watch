# RPi Watch - GC9A01 I2C Display with MQTT Integration

A Python application for Raspberry Pi that displays real-time metrics on a GC9A01 circular 240x240 RGB display (I2C variant) sourced from an MQTT broker.

## Features

- **I2C Display Driver**: Custom driver for GC9A01 circular display via I2C protocol
- **MQTT Integration**: Real-time metric updates from local MQTT broker
- **Circular Rendering**: PIL-based rendering with circular masking for round display
- **Thread-Safe**: Non-blocking MQTT subscriber with thread-safe metric storage
- **Configuration-Driven**: YAML-based configuration for display, MQTT, and metrics
- **Production Grade**: Proper logging, error handling, and graceful shutdown

## Hardware Requirements

- **Raspberry Pi** (v3, v4, or v5)
- **GC9A01 I2C Display** (240x240 circular, I2C variant)
  - VCC: 3.3V or 5V (check your display specs)
  - GND: Ground
  - SDA: I2C Data (GPIO 2 / I2C bus 1)
  - SCL: I2C Clock (GPIO 3 / I2C bus 1)
- **MQTT Broker** on local network (e.g., Mosquitto)

## Installation

### 1. System Setup (One-time)

```bash
# Clone or setup the project directory
cd ~/rpi_watch

# Run system setup script (enables I2C, installs dependencies)
sudo bash scripts/setup_i2c.sh

# Reboot to apply changes
sudo reboot
```

### 2. Verify I2C Hardware

After reboot, verify your display is detected:

```bash
# Scan I2C bus for devices
i2cdetect -y 1

# Output should show something like:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:          -- -- -- -- -- -- -- -- -- -- -- -- --
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 30: -- -- -- -- -- -- -- -- -- -- -- 3c -- -- -- --  <- Your display!
```

**Note the display address** (e.g., 0x3C). You'll need this in the config.

### 3. Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 4. Configuration

Edit `config/config.yaml`:

```yaml
display:
  i2c_address: 0x3C          # Change if needed (from i2cdetect output)
  i2c_bus: 1
  width: 240
  height: 240
  rotation: 0
  refresh_rate_hz: 2

mqtt:
  broker_host: "192.168.1.100"  # Your MQTT broker IP
  broker_port: 1883
  topic: "sensor/metric"
  qos: 1
  keepalive: 60

metric_display:
  decimal_places: 1
  font_size: 80              # Adjust for readability
  unit_label: "°C"           # Optional unit
  text_color: [255, 255, 255]
  background_color: [0, 0, 0]
```

## Testing

### Test I2C Bus Communication

```bash
source venv/bin/activate
python3 scripts/test_i2c_bus.py
```

Expected output:
```
✓ smbus2 library available
Scanning I2C bus 1 for device at 0x3C...
✓ Device detected at 0x3C
✓ I2C communication successful!
```

### Test Display Initialization

```bash
python3 scripts/test_display_init.py
```

This will display test numbers on your screen. If you see numbers appear, hardware is working!

## Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run the application
python3 -m rpi_watch.main
```

Expected output:
```
2026-04-15 12:00:00 - rpi_watch.main - INFO - Initializing RPi Watch application
2026-04-15 12:00:00 - rpi_watch.display.gc9a01_i2c - INFO - GC9A01_I2C driver initialized
2026-04-15 12:00:00 - rpi_watch.display.renderer - INFO - MetricRenderer initialized
2026-04-15 12:00:00 - rpi_watch.mqtt.subscriber - INFO - MQTTSubscriber initialized
2026-04-15 12:00:00 - rpi_watch.main - INFO - All components initialized successfully
2026-04-15 12:00:00 - rpi_watch.main - INFO - Starting main event loop
2026-04-15 12:00:01 - rpi_watch.mqtt.subscriber - INFO - Connected to MQTT broker
2026-04-15 12:00:01 - rpi_watch.mqtt.subscriber - INFO - Subscribed to topic: sensor/metric
2026-04-15 12:00:02 - rpi_watch.main - INFO - Waiting for MQTT metric...
```

The application will display a "..." waiting message until the first metric arrives.

### Publishing Test Metrics

From another terminal or device, publish a metric:

```bash
# Using mosquitto_pub
mosquitto_pub -h 192.168.1.100 -t sensor/metric -m "23.5"

# Or as JSON
mosquitto_pub -h 192.168.1.100 -t sensor/metric -m '{"value": 23.5}'
```

The display should immediately update with the value.

## Project Structure

```
rpi_watch/
├── README.md
├── requirements.txt
├── config/
│   └── config.yaml
├── src/
│   └── rpi_watch/
│       ├── __init__.py
│       ├── main.py
│       ├── display/
│       │   ├── gc9a01_i2c.py       # I2C driver
│       │   └── renderer.py         # PIL rendering
│       ├── mqtt/
│       │   └── subscriber.py       # MQTT client
│       ├── metrics/
│       │   └── metric_store.py     # Thread-safe storage
│       └── utils/
│           └── logging_config.py
└── scripts/
    ├── setup_i2c.sh
    ├── test_i2c_bus.py
    └── test_display_init.py
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| smbus2 | ≥0.4.2 | I2C communication |
| Pillow | ≥10.0.0 | Image rendering |
| paho-mqtt | ≥2.1.0 | MQTT client |
| PyYAML | ≥6.0 | Configuration |

## Troubleshooting

### I2C Bus Not Found
```
Error: I2C bus 1 not found
```

**Solution:**
1. Run `sudo raspi-config` → Interfacing Options → I2C → Enable
2. Reboot: `sudo reboot`
3. Verify: `ls -l /dev/i2c*` should show `/dev/i2c-1`

### Display Not Detected
```
Error: Device not detected at 0x3C
```

**Solution:**
1. Check physical wiring (SDA/SCL/VCC/GND)
2. Verify power supply (adequate current)
3. Try `i2cdetect -y 1` to find actual address
4. Update `config.yaml` with correct address
5. Check if address needs pull-up resistors (typically 4.7kΩ)

### No MQTT Connection
```
Error: Failed to connect to MQTT broker
```

**Solution:**
1. Verify broker IP: `ping 192.168.1.100`
2. Verify broker is running: `mosquitto -v`
3. Check firewall allows port 1883
4. Verify network connectivity: `ip addr`

### Display Shows Garbled Text
```
Display shows pixels but no readable text
```

**Solution:**
1. Adjust `font_size` in config.yaml (try 100+)
2. Check `font_path` points to valid TrueType font
3. Verify color settings (text/background contrast)
4. Try test script: `python3 scripts/test_display_init.py`

## Running as a Service (Optional)

Create systemd service file at `/etc/systemd/system/rpi_watch.service`:

```ini
[Unit]
Description=RPi Watch - GC9A01 MQTT Display
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/rpi_watch
Environment="PATH=/home/pi/rpi_watch/venv/bin"
ExecStart=/home/pi/rpi_watch/venv/bin/python3 -m rpi_watch.main
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rpi_watch
sudo systemctl start rpi_watch
sudo systemctl status rpi_watch
```

View logs:

```bash
sudo journalctl -u rpi_watch -f
```

## Performance Notes

- **I2C Speed**: Runs at standard 100 kHz (check if your RPi supports 400 kHz for faster refresh)
- **Frame Rate**: 2 Hz default (adjustable via `refresh_rate_hz` in config)
- **Update Only on Change**: Display only updates when metric value changes (reduces I2C traffic)
- **Frame Buffer**: ~180 KB per frame (RGB565 format)

## Known Limitations

1. **I2C-variant GC9A01 is rare**: Most GC9A01 displays use SPI. Verify your hardware is I2C before purchasing.
2. **Register map may vary**: Different I2C GC9A01 implementations may use different register addresses. Consult your display datasheet.
3. **Single metric**: Currently displays one metric value. Multiple metrics would require additional rendering logic.

## MQTT Message Format

The subscriber accepts metrics in multiple formats:

```
# Simple numeric value
mosquitto_pub -h broker -t sensor/metric -m "23.5"

# JSON with value field
mosquitto_pub -h broker -t sensor/metric -m '{"value": 23.5}'

# JSON with other fields (uses first numeric value)
mosquitto_pub -h broker -t sensor/metric -m '{"temperature": 23.5, "humidity": 45}'
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Areas for improvement:
- Add support for SPI-variant GC9A01 displays
- Multi-metric display support
- Custom animations/transitions
- Web dashboard for configuration
- Bluetooth support for metric source

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review logs: `journalctl -u rpi_watch -n 50`
3. Run test scripts: `test_i2c_bus.py`, `test_display_init.py`
4. Check GitHub issues: https://github.com/yourusername/rpi_watch/issues
