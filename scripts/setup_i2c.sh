#!/bin/bash
# Setup script for RPi Watch - Enables I2C and installs dependencies

set -e

echo "=========================================="
echo "RPi Watch - I2C Setup Script"
echo "=========================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi"
    echo "Continuing anyway..."
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run with sudo"
    echo "Usage: sudo bash setup_i2c.sh"
    exit 1
fi

echo ""
echo "Step 1: Update system packages"
apt-get update
apt-get upgrade -y

echo ""
echo "Step 2: Install system dependencies"
apt-get install -y \
    python3-dev \
    python3-venv \
    python3-pip \
    i2c-tools \
    libjpeg-dev \
    libharfbuzz0b \
    libwebp6 \
    libtiff5 \
    libopenjp2-7 \
    libjasper1

echo ""
echo "Step 3: Enable I2C interface"
# Check if I2C is already enabled
if ! grep -q "dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then

    # Try newer path first (Pi 5 / Bookworm)
    if [ -f /boot/firmware/config.txt ]; then
        echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
        echo "I2C enabled in /boot/firmware/config.txt"
    elif [ -f /boot/config.txt ]; then
        echo "dtparam=i2c_arm=on" >> /boot/config.txt
        echo "I2C enabled in /boot/config.txt"
    fi
else
    echo "I2C already enabled"
fi

echo ""
echo "Step 4: Verify I2C kernel modules"
if modprobe i2c_bcm2835 2>/dev/null; then
    echo "✓ I2C module loaded"
fi

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Reboot your Raspberry Pi: sudo reboot"
echo "2. After reboot, test I2C detection:"
echo "   i2cdetect -y 1"
echo "3. Look for your display address (commonly 0x3C or 0x3D)"
echo ""
echo "Then test the application:"
echo "cd ~/rpi_watch"
echo "python3 -m venv venv"
echo "source venv/bin/activate"
echo "pip install -r requirements.txt"
echo "python3 scripts/test_i2c_bus.py"
echo ""
