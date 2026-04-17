# RPi Watch Setup Guide

**Last Updated:** April 16, 2026

This guide reflects the current working architecture:
- GC9A01 over SPI
- manual CS framing
- one MQTT subscription feeding a local metric/history store
- config-driven layout selection

## 1. Enable SPI

```bash
sudo raspi-config
```

Enable:
- `Interface Options` -> `SPI`

Reboot if prompted.

Verify:

```bash
ls -la /dev/spidev*
```

You should see at least:

```text
/dev/spidev0.0
/dev/spidev0.1
```

## 2. Install System Dependencies

Recommended:

```bash
sudo bash setup.sh
```

Manual equivalent:

```bash
sudo apt-get update
sudo apt-get install -y \
  python3-dev \
  python3-venv \
  python3-pip \
  git \
  i2c-tools \
  libjpeg-dev \
  fonts-dejavu-core \
  fontconfig

sudo apt-get install -y \
  libharfbuzz0b \
  libwebp6 \
  libtiff5 \
  libopenjp2-7 || echo "Optional Pillow packages may fail on some OS images"
```

Verify the renderer font:

```bash
ls /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
fc-match "DejaVu Sans:style=Bold"
```

## 3. Create The Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## 4. Wire The Display

Use BCM numbering:

| Display | BCM |
|---|---:|
| `SCLK` | `11` |
| `MOSI` | `10` |
| `CS` | `8` |
| `DC` | `25` |
| `RST` | `27` |
| `BLK` | `18` |

Current defaults are already in [config.yaml](/Users/gallar/Documents/workspace/rpi_watch/config/config.yaml).

## 5. Configure MQTT

Update the broker host and topic in [config.yaml](/Users/gallar/Documents/workspace/rpi_watch/config/config.yaml):

```yaml
mqtt:
  broker_host: "192.168.0.214"
  broker_port: 1883
  topic: "airquality/sensor"
```

Verify connectivity from the watch Pi:

```bash
mosquitto_sub -h 192.168.0.214 -t airquality/sensor -v
```

## 6. Render Components Individually

Before running the full app, render each component/layout to `/tmp`:

```bash
PYTHONPATH=src python3 scripts/test_components.py
PYTHONPATH=src python3 scripts/demo_layouts.py
```

Useful outputs now include:
- `/tmp/test_metric_pm25.png`
- `/tmp/test_sparkline_pm25.png`
- `/tmp/test_gradient_ring_temp.png`
- `/tmp/test_layout_pm_bars.png`
- `/tmp/test_layout_metric_ring.png`

## 7. Choose A Layout

All current layout selection is config-driven.

Single metric with sparkline:

```yaml
metric_display:
  layout_mode: "single_metric"
  metric_key: "pm_2_5"
  show_sparkline: true
  sparkline_points: 10
```

PM bars:

```yaml
metric_display:
  layout_mode: "pm_bars"
  pm_bars_title: "PARTICLES"
  pm_bars_unit_label: "µg/m³"
```

Temperature ring:

```yaml
metric_display:
  layout_mode: "metric_ring"
  ring_field: "temp"
  ring_min_value: 0.0
  ring_max_value: 40.0
  ring_start_angle: 135.0
  ring_end_angle: 405.0
```

## 8. Run The App

```bash
source venv/bin/activate
PYTHONPATH=src python3 -m rpi_watch.main
```

If you want to watch only the MQTT path first:

```bash
PYTHONPATH=src python3 scripts/test_mqtt_subscription.py --timeout 20
```

## 9. Production Deployment

On the deployed watch, the app runs as `rpi_watch.service` so it survives SSH logout and starts on boot.

Check the current service state:

```bash
systemctl status rpi_watch
systemctl is-enabled rpi_watch
sudo journalctl -u rpi_watch -f
```

Typical operations:

```bash
sudo systemctl restart rpi_watch
sudo systemctl stop rpi_watch
sudo systemctl start rpi_watch
```

If the service is missing, create `/etc/systemd/system/rpi_watch.service`:

```ini
[Unit]
Description=RPi Watch Display App
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/rpi_watch
Environment=PYTHONPATH=/home/pi/rpi_watch/src
ExecStart=/home/pi/rpi_watch/venv/bin/python3 -m rpi_watch.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rpi_watch
```

Use `mosquitto_sub` only for MQTT diagnostics. It is a foreground tool and stops when the shell exits:

```bash
mosquitto_sub -h 127.0.0.1 -t airquality/sensor -v
```

## 10. Troubleshooting

### Tiny text or broken glyphs

```text
WARNING - No scalable font source could be loaded
```

Fix:

```bash
sudo apt-get install -y fonts-dejavu-core fontconfig
ls /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
fc-match "DejaVu Sans:style=Bold"
```

### MQTT connects but no value is shown

Check the raw topic:

```bash
mosquitto_sub -h 192.168.0.214 -t airquality/sensor -v
```

The watch expects valid JSON payloads for multi-field messages.

### Display renders but animation feels slow

The current config still uses a conservative SPI clock:

```yaml
display:
  spi_speed: 1000000
```

For smoother transitions later, this can be raised after hardware validation.
