#!/bin/bash

################################################################################
#                   RPi WATCH - GC9A01 DISPLAY SETUP SCRIPT                    #
#                                                                              #
# Automated installation, testing, and deployment for Raspberry Pi            #
# System configuration → Install dependencies → Hardware verification        #
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/setup.log"
VENV_DIR="$SCRIPT_DIR/venv"
PROJECT_NAME="RPi Watch"

################################################################################
# Logging Functions
################################################################################

log() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

section() {
    echo "" | tee -a "$LOG_FILE"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}$1${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
}

################################################################################
# System Checks
################################################################################

check_prerequisites() {
    section "CHECKING PREREQUISITES"

    # Check if running on Raspberry Pi
    if ! grep -q "Raspberry" /proc/device-tree/model 2>/dev/null; then
        warn "Not running on Raspberry Pi (detected: $(cat /proc/device-tree/model 2>/dev/null || echo 'unknown'))"
        warn "This script is optimized for Raspberry Pi. Some features may not work."
    else
        success "Running on $(cat /proc/device-tree/model 2>/dev/null)"
    fi

    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed. Install with: sudo apt-get install python3 python3-pip"
    fi
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    success "Python 3 found: $PYTHON_VERSION"

    # Check git
    if ! command -v git &> /dev/null; then
        warn "Git not installed. Install with: sudo apt-get install git"
    else
        success "Git found"
    fi

    # Check SPI
    if [ ! -e /dev/spidev0.0 ]; then
        warn "SPI not detected. Enable with: sudo raspi-config (Interfacing Options → SPI)"
        warn "You must enable SPI before using the display."
    else
        success "SPI bus detected"
    fi
}

################################################################################
# System Configuration
################################################################################

configure_system() {
    section "SYSTEM CONFIGURATION"

    log "Updating package lists..."
    sudo apt-get update 2>&1 | tee -a "$LOG_FILE" > /dev/null

    log "Installing system dependencies..."
    PACKAGES=(
        "python3-dev"
        "python3-venv"
        "python3-pip"
        "git"
        "i2c-tools"
        "libjpeg-dev"
        "fonts-dejavu-core"
        "fontconfig"
    )

    for pkg in "${PACKAGES[@]}"; do
        if dpkg -l | grep -q "^ii  $pkg"; then
            success "$pkg already installed"
        else
            log "Installing $pkg..."
            sudo apt-get install -y "$pkg" 2>&1 | tee -a "$LOG_FILE" > /dev/null
            success "$pkg installed"
        fi
    done

    # Optional: Pillow dependencies (may fail - that's OK)
    log "Installing optional Pillow dependencies (failures are OK)..."
    sudo apt-get install -y \
        libharfbuzz0b \
        libwebp6 \
        libtiff5 \
        libopenjp2-7 2>&1 | tee -a "$LOG_FILE" > /dev/null || warn "Some optional packages failed - this is OK"

    log "Verifying renderer font availability..."
    if [ -f /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf ]; then
        success "Renderer font found: /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    else
        warn "Renderer font not found. Install with: sudo apt-get install fonts-dejavu-core fontconfig"
    fi

    success "System configuration complete"
}

################################################################################
# Python Environment Setup
################################################################################

setup_python_environment() {
    section "SETTING UP PYTHON VIRTUAL ENVIRONMENT"

    if [ -d "$VENV_DIR" ]; then
        warn "Virtual environment already exists at $VENV_DIR"
        read -p "Do you want to recreate it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            success "Using existing virtual environment"
            return
        fi
    fi

    log "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created"

    # Activate it
    source "$VENV_DIR/bin/activate"

    log "Upgrading pip, setuptools, and wheel..."
    pip install --quiet --upgrade pip setuptools wheel 2>&1 | tee -a "$LOG_FILE" > /dev/null
    success "pip/setuptools/wheel upgraded"

    log "Installing project dependencies..."
    pip install -r "$SCRIPT_DIR/requirements.txt" 2>&1 | tee -a "$LOG_FILE" > /dev/null
    success "Project dependencies installed"

    # Verify
    log "Verifying key packages..."
    pip list | grep -E "Pillow|paho|spidev|RPi" | tee -a "$LOG_FILE"
}

################################################################################
# Hardware Verification
################################################################################

verify_hardware() {
    section "VERIFYING HARDWARE"

    source "$VENV_DIR/bin/activate"

    log "Testing SPI bus access..."
    python3 -c "
import spidev
try:
    spi = spidev.SpiDev()
    spi.open(0, 0)
    print(f'  SPI Speed: {spi.max_speed_hz} Hz')
    print(f'  SPI Mode: {spi.mode}')
    spi.close()
    print('  Status: OK')
except Exception as e:
    print(f'  Error: {e}')
    exit(1)
" 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        success "SPI bus verification passed"
    else
        error "SPI bus verification failed. Enable SPI and try again."
    fi

    log "Testing GPIO pin access..."
    python3 -c "
import RPi.GPIO as GPIO
try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(24, GPIO.OUT)
    GPIO.setup(25, GPIO.OUT)
    GPIO.output(24, GPIO.HIGH)
    GPIO.output(25, GPIO.HIGH)
    GPIO.cleanup()
    print('  GPIO 24: OK')
    print('  GPIO 25: OK')
except Exception as e:
    print(f'  Error: {e}')
    exit(1)
" 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        success "GPIO verification passed"
    else
        warn "GPIO verification failed. Run with sudo or check GPIO permissions."
    fi
}

################################################################################
# Run Tests
################################################################################

run_tests() {
    section "RUNNING TEST SUITE"

    source "$VENV_DIR/bin/activate"

    log "Running SPI communication tests..."
    if python3 "$SCRIPT_DIR/scripts/test_spi_bus.py" 2>&1 | tee -a "$LOG_FILE"; then
        success "SPI tests passed"
    else
        warn "SPI tests failed. Check hardware connections."
    fi

    log "Running component rendering tests..."
    if python3 "$SCRIPT_DIR/scripts/test_components.py" 2>&1 | tee -a "$LOG_FILE"; then
        success "Component tests passed"
    else
        warn "Component tests failed. Check if display is connected."
    fi
}

################################################################################
# Configuration
################################################################################

setup_configuration() {
    section "CONFIGURING APPLICATION"

    log "Checking for config file..."
    if [ ! -f "$SCRIPT_DIR/config/config.yaml" ] && [ -f "$SCRIPT_DIR/config/config.yaml.example" ]; then
        cp "$SCRIPT_DIR/config/config.yaml.example" "$SCRIPT_DIR/config/config.yaml"
        success "Created local config.yaml from config.yaml.example"
    fi

    if [ -f "$SCRIPT_DIR/config/config.yaml" ]; then
        success "config.yaml found"

        read -p "Do you want to update the MQTT broker address? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            read -p "Enter MQTT broker IP (default 127.0.0.1): " mqtt_ip
            mqtt_ip=${mqtt_ip:-127.0.0.1}

            # Update config using Python
            python3 << EOF
import yaml

config_file = "$SCRIPT_DIR/config/config.yaml"
with open(config_file) as f:
    config = yaml.safe_load(f)

config['mqtt']['broker_host'] = '$mqtt_ip'

with open(config_file, 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print(f"  MQTT broker updated to: $mqtt_ip")
EOF
            success "Configuration updated"
        fi
    else
        warn "config.yaml not found. Copy config/config.yaml.example to config/config.yaml and review docs/guides/SETUP_GUIDE.md"
    fi
}

################################################################################
# Post-Setup Instructions
################################################################################

print_instructions() {
    section "SETUP COMPLETE! 🎉"

    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo ""
    echo "1. Verify hardware wiring (see docs/guides/SETUP_GUIDE.md):"
    echo "   - GC9A01 Pin 1 (GND) → Raspberry Pi GND"
    echo "   - GC9A01 Pin 2 (VCC) → Raspberry Pi 3.3V"
    echo "   - GC9A01 Pin 3 (CLK) → Raspberry Pi GPIO 11"
    echo "   - GC9A01 Pin 4 (MOSI) → Raspberry Pi GPIO 10"
    echo "   - GC9A01 Pin 5 (RES) → Raspberry Pi GPIO 25"
    echo "   - GC9A01 Pin 6 (DC) → Raspberry Pi GPIO 24"
    echo ""
    echo "2. Verify MQTT broker is running:"
    echo "   mosquitto_sub -h 127.0.0.1 -t airquality/sensor -C 1 -v"
    echo ""
    echo "3. Run the main application:"
    echo "   source $VENV_DIR/bin/activate"
    echo "   python3 -m rpi_watch.main"
    echo ""
    echo "4. For systemd auto-start, see 'Production Deployment' section in docs/guides/SETUP_GUIDE.md"
    echo ""
    echo -e "${GREEN}Setup log saved to: $LOG_FILE${NC}"
    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                  $PROJECT_NAME - Setup Script                ║"
    echo "║           Automated Raspberry Pi Configuration            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    echo "Setup started: $(date)" | tee "$LOG_FILE"

    # Run all setup phases
    check_prerequisites
    configure_system
    setup_python_environment
    verify_hardware
    run_tests
    setup_configuration
    print_instructions

    echo "" | tee -a "$LOG_FILE"
    echo "Setup completed: $(date)" | tee -a "$LOG_FILE"
}

# Run main function
main "$@"
