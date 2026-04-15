# RPi Watch - Complete Setup Guide

**Last Updated**: April 15, 2026
**Target Hardware**: Raspberry Pi 3/4/5 + GC9A01 Display
**Estimated Setup Time**: 30-45 minutes

---

## Table of Contents

1. [Hardware Prerequisites](#hardware-prerequisites)
2. [System Preparation](#system-preparation)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Hardware Verification](#hardware-verification)
6. [Testing](#testing)
7. [Running the Application](#running-the-application)
8. [Production Deployment](#production-deployment)
9. [Troubleshooting](#troubleshooting)

---

## Hardware Prerequisites

### Required Components

1. **Raspberry Pi** (v3, v4, or v5)
   - Minimum 512 MB RAM (1 GB recommended)
   - 8 GB microSD card (recommended)
   - 5V power supply (2A minimum)

2. **GC9A01 Circular Display**
   - 1.28" round TFT display
   - **MUST BE SPI VARIANT** (NOT I2C)
   - 240×240 RGB565 color
   - 7PIN or 8PIN interface

3. **Connecting Wires**
   - 7 male-to-female Dupont wires (20cm)
   - Or breadboard for temporary connections

4. **Optional Components**
   - Pull-up resistors (4.7kΩ, for DC/RST pins)
   - Breadboard (for prototyping)
   - MQTT Broker (separate RPi or computer)

### Verify Display Hardware

⚠️ **CRITICAL**: Confirm your display is the **SPI variant**

Check your display specifications:
- ✅ SPI variant: 7PIN/8PIN interface
- ❌ I2C variant: Uses I2C protocol (incompatible)
- ❌ 8080 variant: Uses parallel interface (incompatible)

If unsure, check the display documentation or ask supplier:
```
Q: "Is this GC9A01 an SPI variant?"
Expected: "Yes, it has SPI interface with MOSI/MISO/SCLK"
```

---

## System Preparation

### Step 1: Update Raspberry Pi OS

```bash
# SSH into your Raspberry Pi (or open terminal)
ssh pi@192.168.x.x
# or use: ssh pi@raspberrypi.local

# Update system packages
sudo apt-get update
sudo apt-get upgrade -y
```

### Step 2: Enable Hardware Interfaces

```bash
# Run configuration tool
sudo raspi-config
```

**Configuration steps** (use arrow keys to navigate):
1. Select: **"3 Interface Options"**
2. Select: **"I5 SPI"**
3. Answer: **"Yes"** to enable SPI
4. Select: **"I1 I2C"** (optional, for future use)
5. Answer: **"Yes"** to enable I2C
6. Select: **"Finish"**
7. Select: **"Yes"** to reboot when prompted

After reboot, verify:
```bash
# Check SPI device files exist
ls -la /dev/spidev*

# Expected output:
# crw------- 1 root root /dev/spidev0.0
# crw------- 1 root root /dev/spidev0.1
```

### Step 3: Install System Dependencies

```bash
# Install required system packages
sudo apt-get install -y \
  python3-dev \
  python3-venv \
  python3-pip \
  i2c-tools \
  libjpeg-dev \
  git

# Optional: Pillow dependencies (may fail on newer OS - skip if not needed)
sudo apt-get install -y \
  libharfbuzz0b \
  libwebp6 \
  libtiff5 \
  libopenjp2-7 || echo "Note: Some optional packages failed - this is OK"

# Verify Python version (should be 3.9+)
python3 --version
```

### Step 4: Give User GPIO Permissions (Optional)

To run GPIO commands without `sudo`:

```bash
# Add user to gpio group
sudo usermod -a -G gpio pi
sudo usermod -a -G spi pi

# Apply group changes (logout and login, or use):
newgrp gpio
newgrp spi

# Verify
groups
# Should include: gpio spi
```

---

## Installation Steps

### Step 1: Clone/Setup Project Directory

```bash
# Navigate to home directory
cd ~

# Create workspace if needed
mkdir -p ~/workspace/rpi_watch
cd ~/workspace/rpi_watch

# If cloning from Git:
# git clone https://github.com/jegb/rpi_watch.git .
# Or copy files to this directory
```

### Step 2: Create Python Virtual Environment (FIRST!)

⚠️ **IMPORTANT**: Create the virtual environment BEFORE installing any packages

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Verify activation (prompt should show (venv) prefix)
which python
# Should output: /home/pi/workspace/rpi_watch/venv/bin/python3

# You MUST activate this environment before installing any packages
```

### Step 3: Install Python Dependencies

```bash
# Now that venv is activated, upgrade pip
pip install --upgrade pip setuptools wheel

# Install project requirements
pip install -r requirements.txt

# Verify key installations
pip list | grep -E "Pillow|paho|spidev|RPi"
```

**Expected output:**
```
Pillow             10.0.0 (or later)
paho-mqtt          2.1.0 (or later)
RPi.GPIO           0.7.0 (or later)
spidev             3.5 (or later)
PyYAML             6.0 (or later)
```

### Step 4: Install Project (Optional)

```bash
# Make sure venv is still activated
pip install -e .
```

**Expected output:**
```
Pillow             10.0.0 (or later)
paho-mqtt          2.1.0 (or later)
RPi.GPIO           0.7.0 (or later)
spidev             3.5 (or later)
PyYAML             6.0 (or later)
```

### Step 4: Install Project (Optional)

For development, you can install in editable mode:

```bash
# Install project in development mode
pip install -e .

# Or skip if just using scripts directly
```

---

## Configuration

### Step 1: Create Main Configuration File

The configuration file should already exist at `config/config.yaml`. Verify:

```bash
cat config/config.yaml
```

### Step 2: Update MQTT Broker Address

Edit `config/config.yaml` and update the MQTT broker:

```yaml
mqtt:
  broker_host: "192.168.0.214"  # Your MQTT broker IP
  broker_port: 1883
  topic: "airquality/sensor"
  qos: 1
  keepalive: 60
  json_field: "pm_2_5"           # Or "temp", "humidity", etc.
```

**Finding your MQTT broker IP:**
```bash
# If running on same network
ping mosquitto.local
# or
ping mqtt.local
# or check your MQTT server IP
```

### Step 3: Verify Configuration

```bash
# Check if config loads correctly
python3 -c "
import yaml
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)
    print('✓ Config loaded successfully')
    print(f'  MQTT Broker: {config[\"mqtt\"][\"broker_host\"]}')
    print(f'  Display SPI Speed: {config[\"display\"][\"spi_speed\"]/1e6:.1f} MHz')
"
```

### Step 4: Optional - Create Local Config

For local overrides without modifying main config:

```bash
# Create local config (git-ignored)
cp config/config.yaml config/config.local.yaml

# Edit local config
nano config/config.local.yaml

# Update main.py to load local config if present
```

---

## Hardware Verification

### Step 1: Verify SPI Bus

```bash
# Check SPI devices
ls -la /dev/spidev*

# Test SPI bus access
python3 -c "
import spidev
spi = spidev.SpiDev()
spi.open(0, 0)
print(f'✓ SPI bus 0.0 opened successfully')
print(f'  Max speed: {spi.max_speed_hz}')
print(f'  Mode: {spi.mode}')
spi.close()
"
```

### Step 2: Verify GPIO Pins

```bash
# Test GPIO pin control
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Test DC pin (GPIO 24)
GPIO.setup(24, GPIO.OUT)
GPIO.output(24, GPIO.HIGH)
print('✓ GPIO 24 set HIGH')
GPIO.output(24, GPIO.LOW)
print('✓ GPIO 24 set LOW')
GPIO.output(24, GPIO.HIGH)

# Test RST pin (GPIO 25)
GPIO.setup(25, GPIO.OUT)
GPIO.output(25, GPIO.HIGH)
print('✓ GPIO 25 set HIGH')
GPIO.output(25, GPIO.LOW)
print('✓ GPIO 25 set LOW')
GPIO.output(25, GPIO.HIGH)

GPIO.cleanup()
print('✓ All GPIO pins working')
"
```

### Step 3: Physical Wiring

Connect your GC9A01 display to Raspberry Pi (8PIN variant):

```
GC9A01 (8PIN)          Raspberry Pi GPIO
─────────────────────────────────────────
Pin 1: GND        ──→  GND (Pin 6, 9, 14, 20, 25, 30, 34, 39)
Pin 2: VCC        ──→  3.3V (Pin 1 or 17)
Pin 3: CLK        ──→  GPIO 11 (SPI Clock - Pin 23)
Pin 4: MOSI       ──→  GPIO 10 (SPI Data - Pin 19)
Pin 5: RES        ──→  GPIO 25 (Reset)
Pin 6: DC         ──→  GPIO 24 (Data/Command)
Pin 7: CS         ──→  GPIO 8 (Chip Select, optional)
                       or GND if not used
Pin 8: BLK        ──→  3.3V (constant) or GPIO PWM
                       (backlight - tie to 3.3V for full brightness)
```

**Important**: Pin order is critical. Double-check against your display before powering on.

**Wiring Best Practices:**
- Use short wires (< 30cm) for SPI
- Separate ground wires (star grounding)
- Keep power lines away from signal lines
- Use breadboard for prototyping
- Check polarity before power-on

### Step 4: Power Verification

```bash
# Check if display powers on (should see backlight)
# Connect power and check:
# ✓ Display backlight illuminates
# ✓ No smoke or burnt smell
# ✓ Reset takes ~100ms to complete

# If no backlight:
# 1. Check VCC/GND connections
# 2. Verify power supply (min 500mA)
# 3. Check polarity
```

---

## Testing

### Step 1: Run SPI Communication Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run comprehensive SPI test
python3 scripts/test_spi_bus.py
```

**Expected output:**
```
======================================================================
RPi Watch - SPI Bus & Display Communication Test Suite
======================================================================

Test: SPI Bus Detection
────────────────────────────────────────────────────────────────────
✓ spidev library available
✓ RPi.GPIO library available
✓ SPI device /dev/spidev0.0 accessible
✅ PASSED: SPI Bus Detection

Test: GPIO Pin Configuration
────────────────────────────────────────────────────────────────────
✓ GPIO pins configured successfully
✓ DC pin toggle successful
✓ RST pin toggle successful
✅ PASSED: GPIO Pin Configuration

[... more tests ...]

TEST SUMMARY
======================================================================
Passed: 8/8
Failed: 0/8
======================================================================
```

### Step 2: Test Display Initialization

```bash
# Test display hardware
python3 scripts/test_display_init.py
```

**Expected output:**
```
======================================================================
RPi Watch - Display Initialization Test
======================================================================

────────────────────────────────────────────────────────────────────
Test: Display Initialization
────────────────────────────────────────────────────────────────────
Initializing display at 0x3C on I2C bus 1...
✓ Display initialized successfully!
✓ Renderer initialized
✓ Displaying test patterns...

Test 1: Displaying number 42
Test 2: Displaying number 99.9
Test 3: Displaying number 0

✓ Display test successful!
If you see numbers on your circular display, hardware is working!
```

### Step 3: Test Component Rendering

```bash
# Test all UI components (generates test images)
python3 scripts/test_components.py
```

**Expected output:**
```
======================================================================
GC9A01 Display - Component Testing Suite
======================================================================

TEST 1: Text Rendering
────────────────────────────────────────────────────────────────────
✓ Saved: /tmp/test_text_xl.png
✓ Saved: /tmp/test_text_large.png
[... more files ...]
✅ Text rendering tests passed

[... more tests ...]

======================================================================
ALL TESTS PASSED ✓
======================================================================

Test images saved to /tmp/test_*.png
```

### Step 4: Test Layout System

```bash
# View all available layouts
python3 scripts/demo_layouts.py
```

This generates demo images showing all 7 layouts with different data.

### Step 5: Run Integration Tests

```bash
# Run comprehensive integration tests
python3 scripts/test_integration.py
```

Tests the entire system working together.

---

## Running the Application

### Step 1: Start MQTT Broker (if not running)

On your MQTT broker machine:

```bash
# Start Mosquitto MQTT broker
mosquitto -v

# Or if installed as service:
sudo systemctl start mosquitto
sudo systemctl status mosquitto
```

### Step 2: Verify MQTT Connectivity

From Raspberry Pi:

```bash
# Test connection to MQTT broker
python3 -c "
import paho.mqtt.client as mqtt
import time

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print('✓ Connected to MQTT broker')
    else:
        print(f'✗ Failed to connect, code {rc}')

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_connect = on_connect
client.connect('192.168.0.214', 1883, 60)
client.loop_start()
time.sleep(2)
client.loop_stop()
"
```

### Step 3: Start Main Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run main application
python3 -m rpi_watch.main
```

**Expected output:**
```
2026-04-15 14:30:00 - rpi_watch.main - INFO - Initializing RPi Watch application
2026-04-15 14:30:00 - rpi_watch.display.gc9a01_spi - INFO - GC9A01_SPI driver initialized
2026-04-15 14:30:00 - rpi_watch.display.gc9a01_spi - INFO - Connected to SPI bus 0.0 at 10.0MHz
2026-04-15 14:30:01 - rpi_watch.display.gc9a01_spi - INFO - Initializing GC9A01 display...
2026-04-15 14:30:01 - rpi_watch.display.gc9a01_spi - INFO - Display initialization complete
2026-04-15 14:30:02 - rpi_watch.mqtt.subscriber - INFO - Connected to MQTT broker: 192.168.0.214:1883
2026-04-15 14:30:02 - rpi_watch.mqtt.subscriber - INFO - Subscribed to topic: airquality/sensor
2026-04-15 14:30:03 - rpi_watch.main - INFO - Waiting for MQTT metric...
```

Display should show "..." (waiting) until first metric arrives.

### Step 4: Publish Test Metric

From another terminal:

```bash
# Publish test metric via MQTT
mosquitto_pub -h 192.168.0.214 -t airquality/sensor -m '{"pm_2_5": 25.5, "temp": 23.0, "humidity": 45.0}'

# Or simple numeric value:
mosquitto_pub -h 192.168.0.214 -t airquality/sensor -m '25.5'
```

**Expected result**: Display updates with the metric value

### Step 5: Stop Application

```bash
# Press Ctrl+C in the application terminal
# Or from another terminal:
killall python3
```

---

## Production Deployment

### Option 1: Systemd Service (Recommended)

Create auto-starting service:

```bash
# Create service file
sudo nano /etc/systemd/system/rpi-watch.service
```

Paste this content:

```ini
[Unit]
Description=RPi Watch - GC9A01 MQTT Display
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/workspace/rpi_watch
Environment="PATH=/home/pi/workspace/rpi_watch/venv/bin"
ExecStart=/home/pi/workspace/rpi_watch/venv/bin/python3 -m rpi_watch.main
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable rpi-watch

# Start service
sudo systemctl start rpi-watch

# Check status
sudo systemctl status rpi-watch

# View logs
sudo journalctl -u rpi-watch -f
```

### Option 2: Cron Job

For periodic startup:

```bash
# Edit crontab
crontab -e

# Add this line to start at boot:
@reboot cd /home/pi/workspace/rpi_watch && source venv/bin/activate && python3 -m rpi_watch.main >> logs/rpi_watch.log 2>&1 &
```

### Option 3: Screen/Tmux Session

For manual persistent sessions:

```bash
# Start in tmux session
tmux new-session -d -s rpi-watch -c /home/pi/workspace/rpi_watch

# Run application in session
tmux send-keys -t rpi-watch "source venv/bin/activate && python3 -m rpi_watch.main" Enter

# Reattach later
tmux attach-session -t rpi-watch

# Detach with Ctrl+B then D
```

### Step: Create Log Directory

```bash
# Create logs directory
mkdir -p ~/workspace/rpi_watch/logs

# Set permissions
chmod 755 ~/workspace/rpi_watch/logs
```

---

## Troubleshooting

### Issue: SPI Device Not Found

```
Error: No such file or directory: '/dev/spidev0.0'
```

**Solution:**
1. Verify SPI is enabled: `sudo raspi-config` → I5 SPI → Yes
2. Reboot: `sudo reboot`
3. Check: `ls -la /dev/spidev*`

### Issue: GPIO Permission Denied

```
Error: No permission to access /sys/class/gpio
```

**Solution:**
1. Add user to gpio group: `sudo usermod -a -G gpio pi`
2. Add user to spi group: `sudo usermod -a -G spi pi`
3. Logout and login: `exit` then reconnect
4. Or run with sudo (not recommended for production)

### Issue: MQTT Connection Failed

```
Error: Failed to connect to MQTT broker
```

**Solution:**
1. Verify broker is running: `mosquitto -v`
2. Check broker IP: `ping 192.168.0.214`
3. Test manually: `mosquitto_sub -h 192.168.0.214 -t airquality/sensor`
4. Update config.yaml with correct IP

### Issue: Display Shows Garbled Pixels

**Solution:**
1. Lower SPI speed: `spi_speed: 5000000` (5 MHz)
2. Check power supply (needs adequate current)
3. Verify all wire connections
4. Check cable length (keep short)

### Issue: Text Is Unreadable

**Solution:**
1. Use larger text sizes
2. Increase contrast (white on black)
3. Test with `test_components.py`
4. Adjust font size in config

### Issue: Application Crashes

**Solution:**
1. Check logs: `journalctl -u rpi-watch -n 50`
2. Run in terminal to see full error: `python3 -m rpi_watch.main`
3. Verify all dependencies: `pip list`
4. Check hardware connections

### Issue: No Metric Updates on Display

**Solution:**
1. Verify MQTT broker is running
2. Test with `mosquitto_pub` manually
3. Check topic name in config: `mqtt.topic`
4. Check JSON field name: `mqtt.json_field`
5. Monitor MQTT traffic: `mosquitto_sub -h 192.168.0.214 -v -t '#'`

### Issue: Display Refresh Is Slow

**Solution:**
1. Increase SPI speed: `spi_speed: 20000000` (20 MHz)
2. Reduce refresh rate: `refresh_rate_hz: 2` (instead of 5)
3. Check CPU usage: `top`
4. Optimize other processes

---

## Quick Reference

### Essential Commands

```bash
# Activate environment
source venv/bin/activate

# Run main app
python3 -m rpi_watch.main

# Run tests
python3 scripts/test_spi_bus.py
python3 scripts/test_display_init.py
python3 scripts/test_components.py

# View logs
sudo journalctl -u rpi-watch -f

# Stop service
sudo systemctl stop rpi-watch

# Check status
sudo systemctl status rpi-watch
```

### Config File Locations

```
Main config:        ~/workspace/rpi_watch/config/config.yaml
Local config:       ~/workspace/rpi_watch/config/config.local.yaml
Application code:   ~/workspace/rpi_watch/src/rpi_watch/
Scripts:            ~/workspace/rpi_watch/scripts/
Logs:               ~/workspace/rpi_watch/logs/
```

### Default Pin Configuration

```
GPIO 11: Clock (CLK) - hardware SPI
GPIO 10: MOSI (data) - hardware SPI
GPIO 25: Reset (RES)
GPIO 24: Data/Command (DC)
GPIO 8:  Chip Select (CS) - optional, can tie to GND
```

**These match the 8PIN display variant:**
- Pin 3 (CLK) → GPIO 11
- Pin 4 (MOSI) → GPIO 10
- Pin 5 (RES) → GPIO 25
- Pin 6 (DC) → GPIO 24
- Pin 7 (CS) → GPIO 8

---

## Success Checklist

After setup, verify all items:

- [ ] Raspberry Pi OS updated
- [ ] SPI interface enabled
- [ ] Python 3.9+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] SPI bus verified (`/dev/spidev0.0` exists)
- [ ] GPIO pins functional
- [ ] Display wired correctly
- [ ] Display powers on (backlight visible)
- [ ] SPI tests pass (`test_spi_bus.py`)
- [ ] Display tests pass (`test_display_init.py`)
- [ ] Component tests pass (`test_components.py`)
- [ ] MQTT broker running
- [ ] MQTT connection works
- [ ] Main app starts without errors
- [ ] Metric display updates when MQTT data arrives
- [ ] Service auto-starts on reboot

---

## Next Steps

Once setup is complete:

1. **Customize the Display**
   - Edit `config/config.yaml` to select different layout
   - Change color scheme
   - Adjust refresh rate

2. **Connect Real Data**
   - Point to production MQTT broker
   - Change metric topic
   - Select metric field to display

3. **Monitor & Optimize**
   - Review logs regularly
   - Monitor CPU/memory usage
   - Optimize SPI speed for your setup
   - Fine-tune refresh rate

4. **Advanced Features**
   - Add additional layouts
   - Create custom color schemes
   - Implement touch controls
   - Add data logging

---

## Support & Documentation

For detailed information, refer to:

- **README.md** - Quick overview
- **DISPLAY_SYSTEM_GUIDE.md** - Display system details
- **LAYOUTS_AND_COMPONENTS.md** - Component reference
- **HARDWARE_NOTES.md** - Hardware specifications
- **INTEGRATION_SPS_MONITOR.md** - MQTT integration
- **SPI_DRIVER_IMPLEMENTATION.md** - SPI driver details
- **PROJECT_STATUS.md** - Project summary

---

## Getting Help

If you encounter issues:

1. **Check Logs**
   ```bash
   sudo journalctl -u rpi-watch -n 100
   ```

2. **Run Diagnostic Tests**
   ```bash
   python3 scripts/test_spi_bus.py
   python3 scripts/test_display_init.py
   ```

3. **Test MQTT Connectivity**
   ```bash
   mosquitto_sub -h 192.168.0.214 -t airquality/sensor
   ```

4. **Check Hardware**
   - Verify GPIO pins with continuity tester
   - Check power supply voltage
   - Verify display is powered on

5. **Review Documentation**
   - Check troubleshooting section above
   - Read relevant guide documents
   - Search documentation for error message

---

**Setup Complete!** 🎉

Your RPi Watch system is now ready to display real-time metrics from your MQTT broker on the GC9A01 circular display.

For questions or issues, refer to the documentation files or review the troubleshooting section above.
