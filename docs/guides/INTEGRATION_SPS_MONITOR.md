# RPi Watch Integration with SPS Monitor

This document explains how to integrate the RPi Watch circular display with your existing SPS Monitor air quality sensor system.

## Overview

The SPS Monitor project publishes air quality sensor data (PM measurements, temperature, humidity) to an MQTT broker. The RPi Watch subscribes to this data and displays a selected metric on a 240x240 circular I2C display.

## Network Setup

```
┌─────────────────────┐
│   SPS Monitor RPi   │
│   (sensor readings) │──┐
└─────────────────────┘  │
                         │  MQTT Topic: airquality/sensor
                         │  Broker: 192.168.0.214:1883
                         │
                    ┌────▼─────────────────┐
                    │ MQTT Broker          │
                    │ (192.168.0.214:1883) │
                    └────┬─────────────────┘
                         │
                         │
┌─────────────────────────▼──────────────┐
│   RPi Watch Display RPi                │
│   GC9A01 I2C Display (240x240)         │
│   Shows: PM2.5, Temp, or Humidity      │
└────────────────────────────────────────┘
```

## Configuration

The RPi Watch is pre-configured to connect to the SPS Monitor MQTT broker at `192.168.0.214` and subscribe to `airquality/sensor`.

### Default Configuration (PM2.5 Display)

In `config/config.yaml`:

```yaml
mqtt:
  broker_host: "192.168.0.214"
  broker_port: 1883
  topic: "airquality/sensor"
  json_field: "pm_2_5"  # Extract PM2.5 value from JSON

metric_display:
  decimal_places: 1
  unit_label: "µm"      # µg/m³ unit
```

### Switching Display Metrics

To display a different metric from the SPS Monitor, edit `config/config.yaml`:

#### Option 1: Display Temperature (°C)
```yaml
mqtt:
  json_field: "temp"

metric_display:
  unit_label: "°C"
```

#### Option 2: Display Humidity (%)
```yaml
mqtt:
  json_field: "humidity"

metric_display:
  unit_label: "%"
```

#### Option 3: Display PM10
```yaml
mqtt:
  json_field: "pm_10_0"

metric_display:
  unit_label: "µm"
```

## SPS Monitor Data Format

The SPS Monitor publishes the following JSON to `airquality/sensor`:

```json
{
  "pm_1_0": 12.3,
  "pm_2_5": 18.5,
  "pm_4_0": 22.1,
  "pm_10_0": 25.7,
  "temp": 23.5,
  "humidity": 45.0
}
```

**Available fields for `json_field` in config.yaml:**
- `"pm_1_0"` - Particulate matter 1.0 µm
- `"pm_2_5"` - Particulate matter 2.5 µm (default)
- `"pm_4_0"` - Particulate matter 4.0 µm
- `"pm_10_0"` - Particulate matter 10 µm
- `"temp"` - Temperature in °C
- `"humidity"` - Relative humidity in %

## Hardware Setup

### Raspberry Pi Identification

If you're running RPi Watch on a different RPi than the SPS Monitor:

1. **SPS Monitor RPi**: Continues running `sensor_reader.py` for sensor readings
2. **RPi Watch Display RPi**: Runs `rpi_watch` application to display metrics

Both RPis must be on the same network and able to reach the MQTT broker at `192.168.0.214`.

### GC9A01 Display Connection

Connect the I2C display to the RPi Watch device:
- **VCC**: 3.3V or 5V (check display spec)
- **GND**: Ground
- **SDA**: GPIO 2 (I2C data)
- **SCL**: GPIO 3 (I2C clock)

## Starting the Application

### On RPi Watch Device

```bash
cd ~/rpi_watch
source venv/bin/activate
python3 -m rpi_watch.main
```

Expected startup sequence:
1. Connects to I2C display
2. Initializes display with test pattern
3. Connects to MQTT broker (192.168.0.214)
4. Subscribes to `airquality/sensor` topic
5. Displays "..." (waiting for first metric)
6. Once SPS Monitor publishes data, display updates with real-time metrics

## Troubleshooting

### Display shows "..." (waiting for data)

**Cause**: RPi Watch not receiving MQTT messages

**Solutions**:
1. Verify MQTT broker is running:
   ```bash
   mosquitto -v
   ```

2. Check SPS Monitor is publishing:
   ```bash
   # On SPS Monitor RPi
   tail -f sps30_data.log  # Check for recent logs
   ```

3. Verify network connectivity:
   ```bash
   # On RPi Watch
   ping 192.168.0.214
   ```

4. Check broker connection manually:
   ```bash
   mosquitto_sub -h 192.168.0.214 -t airquality/sensor
   ```

### MQTT broker IP is different

If your MQTT broker is at a different IP address, update `config/config.yaml`:

```yaml
mqtt:
  broker_host: "192.168.x.x"  # Your broker IP
```

Then restart the application.

### Wrong field displayed

Check that `json_field` matches an available field name:

```bash
# Monitor MQTT topic to see available fields
mosquitto_sub -h 192.168.0.214 -t airquality/sensor
```

Sample output:
```
{'pm_1_0': 10.2, 'pm_2_5': 15.3, 'pm_4_0': 18.1, 'pm_10_0': 22.5, 'temp': 23.5, 'humidity': 45.0}
```

Update `json_field` to a field name that exists in the payload.

### Display shows wrong value

Check the logs:
```bash
# If running in terminal, watch for error messages
# If running as service, check logs
sudo journalctl -u rpi_watch -f
```

Look for messages like:
```
Field 'pm_2_5' not found in JSON. Available fields: pm_1_0, pm_2_5, ...
```

## Multi-Display Setup

You can run multiple RPi Watch devices, each displaying different metrics:

1. **Display 1**: PM2.5 (default)
   ```yaml
   json_field: "pm_2_5"
   ```

2. **Display 2**: Temperature
   ```yaml
   json_field: "temp"
   unit_label: "°C"
   ```

3. **Display 3**: Humidity
   ```yaml
   json_field: "humidity"
   unit_label: "%"
   ```

Each device connects independently to the MQTT broker and updates in real-time.

## Performance Notes

- **Update Frequency**: The display refreshes when values change (typically every 30-60 seconds when SPS Monitor publishes)
- **Latency**: <100ms from MQTT broker to display (network dependent)
- **Accuracy**: Inherits accuracy from SPS Monitor sensor readings

## Advanced: Custom Data Processing

If you need to modify how data is extracted or processed:

1. Edit `src/rpi_watch/mqtt/subscriber.py`
2. Modify the `_on_message()` method to add custom logic
3. Restart the application

Example: Scaling temperature from Celsius to Fahrenheit
```python
if self.json_field == "temp":
    celsius = float(data["temp"])
    value = (celsius * 9/5) + 32  # Convert to Fahrenheit
else:
    value = float(data[self.json_field])
```

## Monitoring

View real-time metrics from the MQTT broker:

```bash
# Watch all SPS Monitor data
mosquitto_sub -h 192.168.0.214 -t "airquality/sensor" -v

# Watch all RPi Watch activity
sudo journalctl -u rpi_watch -f --all
```

## Related Documentation

- **README.md**: General setup and hardware requirements
- **ARCHITECTURE.md**: System design and data flow
- **config.sps_monitor_examples.yaml**: Configuration examples for each metric
