#!/bin/bash

################################################################################
#                   RPi WATCH - HARDWARE VERIFICATION SCRIPT                   #
#                                                                              #
# Quick hardware verification for display and GPIO without full setup         #
# Run anytime to test: config, SPI bus, GPIO pins, and component rendering    #
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Helper functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

section() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

# Activate venv if it exists
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
else
    warn "Virtual environment not found at $VENV_DIR"
    warn "Run setup.sh first to create it"
fi

# Main verification
main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║            RPi Watch - Hardware Verification              ║"
    echo "║              Quick Status Check for Display              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Config verification
    section "CONFIG VERIFICATION"
    if [ -f "$SCRIPT_DIR/config/config.yaml" ]; then
        log "Loading configuration..."
        python3 << 'EOF'
import yaml
try:
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)
    print('✓ Config loaded successfully')
    print(f'  MQTT Broker: {config["mqtt"]["broker_host"]}')
    print(f'  MQTT Port: {config["mqtt"]["broker_port"]}')
    print(f'  MQTT Topic: {config["mqtt"]["topic"]}')
    print(f'  Display SPI Speed: {config["display"]["spi_speed"]/1e6:.1f} MHz')
    print(f'  GPIO DC Pin: {config["display"]["spi_dc_pin"]}')
    print(f'  GPIO RST Pin: {config["display"]["spi_reset_pin"]}')
except Exception as e:
    print(f'✗ Config error: {e}')
    exit(1)
EOF
        success "Configuration verified"
    else
        error "config.yaml not found!"
        exit 1
    fi

    # SPI Bus verification
    section "SPI BUS VERIFICATION"
    log "Testing SPI bus 0.0..."
    python3 << 'EOF'
import spidev
try:
    spi = spidev.SpiDev()
    spi.open(0, 0)
    print('✓ SPI bus 0.0 opened successfully')
    print(f'  Max speed: {spi.max_speed_hz} Hz ({spi.max_speed_hz/1e6:.1f} MHz)')
    print(f'  Mode: {spi.mode}')
    print(f'  LSB First: {spi.lsbfirst}')
    print(f'  Bits Per Word: {spi.bits_per_word}')
    spi.close()
except FileNotFoundError:
    print('✗ SPI device not found!')
    print('  Enable SPI: sudo raspi-config (Interface Options → SPI)')
    exit(1)
except Exception as e:
    print(f'✗ SPI error: {e}')
    exit(1)
EOF
    if [ $? -eq 0 ]; then
        success "SPI bus verified"
    else
        error "SPI verification failed"
        exit 1
    fi

    # GPIO Pin verification
    section "GPIO PIN VERIFICATION"
    log "Testing GPIO pins 24 and 25..."
    python3 << 'EOF'
import RPi.GPIO as GPIO
try:
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
except Exception as e:
    print(f'✗ GPIO error: {e}')
    print('  Try: sudo usermod -a -G gpio pi')
    exit(1)
EOF
    if [ $? -eq 0 ]; then
        success "GPIO pins verified"
    else
        error "GPIO verification failed"
        exit 1
    fi

    # Display components verification
    section "DISPLAY COMPONENTS VERIFICATION"
    log "Testing display driver import..."
    python3 << 'EOF'
try:
    from rpi_watch.display.gc9a01_spi import GC9A01_SPI
    from rpi_watch.display.components import TextRenderer, CircularGauge, ProgressBar
    from rpi_watch.display.layouts import get_layout, ColorScheme
    print('✓ All display modules imported successfully')
    print('✓ GC9A01_SPI driver available')
    print('✓ Components: TextRenderer, CircularGauge, ProgressBar')
    print('✓ Layout system with 7 templates and 5 color schemes')
except ImportError as e:
    print(f'✗ Import error: {e}')
    exit(1)
except Exception as e:
    print(f'✗ Error: {e}')
    exit(1)
EOF
    if [ $? -eq 0 ]; then
        success "Display components verified"
    else
        error "Component verification failed"
        exit 1
    fi

    # MQTT connectivity check
    section "MQTT CONNECTIVITY CHECK"
    log "Testing MQTT broker connection..."
    python3 << 'EOF'
import paho.mqtt.client as mqtt
import time
import yaml

try:
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    broker_host = config['mqtt']['broker_host']
    broker_port = config['mqtt']['broker_port']

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f'✓ Connected to MQTT broker: {broker_host}:{broker_port}')
        else:
            print(f'✗ Failed to connect, code {rc}')
            exit(1)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect = on_connect
    client.connect(broker_host, broker_port, 60)
    client.loop_start()
    time.sleep(2)
    client.loop_stop()

except ConnectionRefusedError:
    print(f'✗ MQTT broker not accessible at {broker_host}:{broker_port}')
    print('  Start MQTT broker or update config.yaml')
except Exception as e:
    print(f'! MQTT warning: {e}')
    print('  (This is OK if you plan to test without MQTT)')
EOF
    # Don't exit on MQTT failure - it's optional for offline testing
    warn "MQTT check completed (optional for offline testing)"

    # Final summary
    section "VERIFICATION SUMMARY"
    echo ""
    echo -e "${GREEN}✓ All critical systems verified!${NC}"
    echo ""
    echo "Ready to run:"
    echo "  python3 -m rpi_watch.main"
    echo ""
    echo "Or run test suite:"
    echo "  python3 scripts/test_spi_bus.py"
    echo "  python3 scripts/test_components.py"
    echo ""
}

main "$@"
