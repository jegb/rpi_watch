#!/usr/bin/env python3
"""Saleae-oriented SPI debug harness for GC9A01 direct-SPI bring-up.

This script gives you a repeatable transaction sequence to correlate with a
Saleae capture. It can operate in two modes:

1. Manual capture mode:
   - emits a configurable marker GPIO pulse pattern
   - writes a JSONL event log with relative timestamps
   - runs deterministic reset/init/probe/pattern steps

2. Logic 2 automation mode (optional):
   - starts a Saleae capture through the official automation API
   - optionally uses the marker line as a digital trigger
   - saves a .sal capture and raw CSV export

The goal is to debug the SPI interface itself, not just the rendered output.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

# Add src directory to path.
SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

GC9A01_MODULE_PATH = SRC_DIR / "rpi_watch" / "display" / "gc9a01_spi.py"
GC9A01_SPEC = importlib.util.spec_from_file_location("saleae_gc9a01_spi", GC9A01_MODULE_PATH)
if GC9A01_SPEC is None or GC9A01_SPEC.loader is None:
    raise RuntimeError(f"Unable to load GC9A01 SPI driver from {GC9A01_MODULE_PATH}")
GC9A01_MODULE = importlib.util.module_from_spec(GC9A01_SPEC)
GC9A01_SPEC.loader.exec_module(GC9A01_MODULE)
GC9A01_SPI = GC9A01_MODULE.GC9A01_SPI

from rpi_watch.utils import setup_logging

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

try:
    from saleae import automation as saleae_automation
except ImportError:
    saleae_automation = None


DEFAULT_STEPS = ["init", "probe", "window-pattern"]
DEFAULT_READ_PROBES = ["0x04:4", "0x09:4", "0x0A:1", "0x0C:1"]
STEP_CHOICES = [
    "reset",
    "init",
    "probe",
    "window-pattern",
    "full-white",
    "software-reset",
    "sleep-in",
    "sleep-out",
    "display-off",
    "display-on",
    "invert-off",
    "invert-on",
    "all-pixels-off",
    "all-pixels-on",
    "normal-on",
]


def _load_display_defaults(config_path: Path) -> dict[str, Any]:
    """Load display defaults from the app config when available."""
    if not config_path.exists():
        return {}

    if yaml is None:
        logger.warning("PyYAML not installed; ignoring config file defaults")
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    return config.get("display", {})


def _parse_int(value: str) -> int:
    """Parse decimal or prefixed integer input."""
    return int(value, 0)


def _parse_optional_int(value: str) -> Optional[int]:
    """Parse an integer-or-none CLI option."""
    lowered = value.strip().lower()
    if lowered in {"none", "null"}:
        return None
    return _parse_int(value)


def _infer_logical_spi_cs_gpio(spi_bus: int, spi_device: int) -> Optional[int]:
    """Infer the hardware SPI chip-select GPIO for common Raspberry Pi SPI buses."""
    return GC9A01_SPI.infer_chip_select_gpio(spi_bus, spi_device)


def _parse_probe_spec(spec: str) -> tuple[int, int]:
    """Parse a read probe specification like `0x04:4`."""
    command_text, _, length_text = spec.partition(":")
    if not command_text or not length_text:
        raise ValueError(f"Invalid probe spec: {spec!r}. Expected COMMAND:LENGTH.")

    command = _parse_int(command_text)
    length = _parse_int(length_text)

    if not 0 <= command <= 0xFF:
        raise ValueError(f"Probe command out of byte range: {command_text}")
    if length <= 0:
        raise ValueError(f"Probe length must be positive: {length_text}")

    return command, length


def _panel_cs_description(
    panel_cs_gpio: Optional[int],
    logical_spi_cs_gpio: Optional[int],
    manual_cs: bool,
) -> str:
    """Describe how panel chip select is expected to be handled for this run."""
    if manual_cs and panel_cs_gpio is not None:
        return f"manual GPIO{panel_cs_gpio}"
    if manual_cs and logical_spi_cs_gpio is not None:
        return f"manual inferred GPIO{logical_spi_cs_gpio}"
    if logical_spi_cs_gpio is not None:
        return f"hardware SPI CE on GPIO{logical_spi_cs_gpio}"
    return "unmanaged / tied low"


def _hex_preview(data: bytes, limit: int = 32) -> str:
    """Return a short hex preview for logs and event files."""
    preview = data[:limit].hex(" ").upper()
    if len(data) > limit:
        return f"{preview} ... (+{len(data) - limit} bytes)"
    return preview


def _build_window_pattern(size: int) -> bytes:
    """Build a small deterministic RGB565 pattern for Saleae correlation."""
    colors = (
        0xF800,  # red
        0x07E0,  # green
        0x001F,  # blue
        0xFFFF,  # white
        0x0000,  # black
        0xFFE0,  # yellow
        0xF81F,  # magenta
        0x07FF,  # cyan
    )

    payload = bytearray()
    for y in range(size):
        for x in range(size):
            color = colors[((x // 2) + (y // 2)) % len(colors)]
            payload.extend(struct.pack(">H", color))
    return bytes(payload)


@dataclass
class EventRecorder:
    """Append-only JSONL event recorder."""

    output_dir: Path

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._start_ns = time.monotonic_ns()
        self._events_path = self.output_dir / "events.jsonl"

    def record(self, kind: str, **fields: Any) -> dict[str, Any]:
        """Record a timestamped event to disk."""
        now_ns = time.monotonic_ns()
        event = {
            "t_rel_ns": now_ns - self._start_ns,
            "t_rel_s": round((now_ns - self._start_ns) / 1_000_000_000, 9),
            "kind": kind,
            **fields,
        }

        with self._events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

        return event

    def write_metadata(self, **metadata: Any) -> None:
        """Write a run metadata file."""
        metadata_path = self.output_dir / "run_metadata.json"
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, sort_keys=True)


class MarkerPin:
    """Drive a dedicated GPIO marker line for Saleae alignment."""

    def __init__(self, pin: Optional[int]):
        self.pin = pin

    @property
    def enabled(self) -> bool:
        return self.pin is not None

    def setup(self) -> None:
        if not self.enabled:
            return
        if GPIO is None:
            raise RuntimeError("RPi.GPIO not installed. Install via: pip install RPi.GPIO")

        try:
            GPIO.setmode(GPIO.BCM)
        except RuntimeError:
            pass
        GPIO.setwarnings(False)
        GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)

    def pulse(self, count: int, high_seconds: float, low_seconds: float) -> None:
        if not self.enabled:
            return

        for index in range(count):
            GPIO.output(self.pin, GPIO.HIGH)
            time.sleep(high_seconds)
            GPIO.output(self.pin, GPIO.LOW)
            if index != count - 1:
                time.sleep(low_seconds)

    def cleanup(self) -> None:
        if self.enabled:
            GPIO.output(self.pin, GPIO.LOW)


class SaleaeTracingDisplay(GC9A01_SPI):
    """GC9A01 driver wrapper that records command/data timing."""

    def __init__(self, *args: Any, recorder: EventRecorder, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.recorder = recorder

    def connect(self):
        self.recorder.record(
            "connect_start",
            spi_bus=self.spi_bus,
            spi_device=self.spi_device,
            spi_speed_hz=self.spi_speed,
            manual_cs=self.manual_cs,
            panel_cs_gpio=self.cs_pin,
            logical_spi_cs_gpio=_infer_logical_spi_cs_gpio(self.spi_bus, self.spi_device),
        )
        super().connect()
        self.recorder.record("connect_complete")

    def reset(self):
        self.recorder.record("reset_start")
        super().reset()
        self.recorder.record("reset_complete")

    def _write_command(self, command: int):
        self.recorder.record("spi_command", command=command, command_hex=f"0x{command:02X}")
        super()._write_command(command)

    def _write_data(self, data: bytes):
        self.recorder.record(
            "spi_data",
            length=len(data),
            preview_hex=_hex_preview(data),
        )
        super()._write_data(data)

    def read_register(self, command: int, length: int, dummy_byte: int = 0x00) -> bytes:
        """Attempt to read a controller register over SPI.

        Many GC9A01 modules are write-only or do not expose a usable MISO path.
        In that case this will return zeros, but it is still useful to capture.
        """
        if not self.spi:
            raise RuntimeError("SPI not connected. Call connect() first.")

        self._begin_transaction()
        try:
            GPIO.output(self.dc_pin, GPIO.LOW)
            self._spi_write(bytes([command]))
            self.recorder.record(
                "spi_read_command",
                command=command,
                command_hex=f"0x{command:02X}",
                length=length,
            )

            GPIO.output(self.dc_pin, GPIO.HIGH)
            response = bytes(self.spi.xfer2([dummy_byte] * length))
            self.recorder.record(
                "spi_read_response",
                command=command,
                command_hex=f"0x{command:02X}",
                length=length,
                response_hex=response.hex(" ").upper(),
            )
            return response
        finally:
            self._end_transaction()


class SaleaeAutomationController:
    """Optional Logic 2 automation wrapper."""

    def __init__(
        self,
        output_dir: Path,
        enabled_channels: list[int],
        digital_sample_rate: int,
        digital_threshold_volts: Optional[float],
        port: int,
        device_id: Optional[str],
        capture_seconds: float,
        marker_channel: Optional[int],
        use_trigger: bool,
        launch_logic2: bool,
        logic2_path: Optional[str],
        recorder: EventRecorder,
    ):
        self.output_dir = output_dir
        self.enabled_channels = enabled_channels
        self.digital_sample_rate = digital_sample_rate
        self.digital_threshold_volts = digital_threshold_volts
        self.port = port
        self.device_id = device_id
        self.capture_seconds = capture_seconds
        self.marker_channel = marker_channel
        self.use_trigger = use_trigger
        self.launch_logic2 = launch_logic2
        self.logic2_path = logic2_path
        self.recorder = recorder

    def run(self, callback, analyzer_settings: dict[str, Any], raw_channels: list[int]) -> None:
        """Run a Saleae-managed capture around the provided callback."""
        if saleae_automation is None:
            raise RuntimeError(
                "logic2-automation is not installed. Install with: pip install logic2-automation"
            )

        manager_factory = saleae_automation.Manager.launch if self.launch_logic2 else saleae_automation.Manager.connect
        manager_kwargs: dict[str, Any] = {"port": self.port, "connect_timeout_seconds": 10.0}
        if self.launch_logic2 and self.logic2_path:
            manager_kwargs["application_path"] = self.logic2_path

        with manager_factory(**manager_kwargs) as manager:
            app_info = manager.get_app_info()
            devices = manager.get_devices()
            self.recorder.record(
                "saleae_manager_ready",
                app_version=app_info.app_version,
                api_version=f"{app_info.api_version.major}.{app_info.api_version.minor}.{app_info.api_version.patch}",
                connected_devices=[device.device_id for device in devices],
            )

            device_configuration = saleae_automation.LogicDeviceConfiguration(
                enabled_digital_channels=self.enabled_channels,
                digital_sample_rate=self.digital_sample_rate,
                digital_threshold_volts=self.digital_threshold_volts,
            )

            if self.use_trigger:
                capture_mode = saleae_automation.DigitalTriggerCaptureMode(
                    trigger_type=saleae_automation.DigitalTriggerType.RISING,
                    trigger_channel_index=self.marker_channel,
                    after_trigger_seconds=self.capture_seconds,
                )
            else:
                capture_mode = saleae_automation.TimedCaptureMode(duration_seconds=self.capture_seconds)

            capture_configuration = saleae_automation.CaptureConfiguration(capture_mode=capture_mode)

            with manager.start_capture(
                device_id=self.device_id,
                device_configuration=device_configuration,
                capture_configuration=capture_configuration,
            ) as capture:
                self.recorder.record(
                    "saleae_capture_started",
                    enabled_channels=self.enabled_channels,
                    digital_sample_rate=self.digital_sample_rate,
                    capture_mode="trigger" if self.use_trigger else "timed",
                )

                callback()

                if self.use_trigger:
                    capture.wait()
                else:
                    # Ensure the callback ran before waiting for the timed capture to drain.
                    capture.wait()

                capture_path = self.output_dir / "logic_capture.sal"
                capture.save_capture(filepath=str(capture_path))

                raw_dir = self.output_dir / "raw_csv"
                raw_dir.mkdir(exist_ok=True)
                capture.export_raw_data_csv(
                    directory=str(raw_dir),
                    digital_channels=raw_channels,
                )

                analyzer_path: Optional[Path] = None
                try:
                    spi_analyzer = capture.add_analyzer(
                        "SPI",
                        label="GC9A01 SPI",
                        settings=analyzer_settings,
                    )
                    analyzer_path = self.output_dir / "spi_export.csv"
                    capture.export_data_table(
                        filepath=str(analyzer_path),
                        analyzers=[spi_analyzer],
                    )
                    self.recorder.record("saleae_analyzer_exported", path=str(analyzer_path))
                except Exception as exc:
                    logger.warning("Saleae analyzer export skipped: %s", exc)
                    self.recorder.record("saleae_analyzer_export_failed", error=str(exc))

                self.recorder.record(
                    "saleae_capture_saved",
                    capture_path=str(capture_path),
                    raw_dir=str(raw_dir),
                    analyzer_path=str(analyzer_path) if analyzer_path else None,
                )


def _resolve_output_dir(base_dir: Path) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_dir = base_dir / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _resolve_steps(step_args: list[str]) -> list[str]:
    if not step_args:
        return list(DEFAULT_STEPS)
    return step_args


def _saleae_analyzer_settings(
    clock_channel: Optional[int],
    mosi_channel: Optional[int],
    miso_channel: Optional[int],
    cs_channel: Optional[int],
) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "Bits per Transfer": "8 Bits per Transfer (Standard)",
    }
    if clock_channel is not None:
        settings["Clock"] = clock_channel
    if mosi_channel is not None:
        settings["MOSI"] = mosi_channel
    if miso_channel is not None:
        settings["MISO"] = miso_channel
    if cs_channel is not None:
        settings["Enable"] = cs_channel
    return settings


def _countdown(seconds: float, description: str) -> None:
    if seconds <= 0:
        return

    logger.info("%s in %.2f seconds...", description, seconds)
    time.sleep(seconds)


def _run_steps(
    display: SaleaeTracingDisplay,
    steps: list[str],
    recorder: EventRecorder,
    marker: MarkerPin,
    marker_high_s: float,
    marker_low_s: float,
    read_probes: list[tuple[int, int]],
    window_x: int,
    window_y: int,
    window_size: int,
) -> None:
    step_pulses = {
        "reset": 1,
        "init": 2,
        "probe": 3,
        "window-pattern": 4,
        "full-white": 5,
        "software-reset": 6,
        "sleep-in": 7,
        "sleep-out": 8,
        "display-off": 9,
        "display-on": 10,
        "invert-off": 11,
        "invert-on": 12,
        "all-pixels-off": 13,
        "all-pixels-on": 14,
        "normal-on": 15,
    }

    for step in steps:
        recorder.record("step_start", step=step)
        marker.pulse(step_pulses.get(step, 1), marker_high_s, marker_low_s)

        if step == "reset":
            display.reset()
        elif step == "init":
            display.init_display()
        elif step == "probe":
            for command, length in read_probes:
                response = display.read_register(command, length)
                logger.info(
                    "Read 0x%02X -> %s",
                    command,
                    response.hex(" ").upper(),
                )
        elif step == "window-pattern":
            if not display.initialized:
                raise RuntimeError("window-pattern step requires the display to be initialized first")
            payload = _build_window_pattern(window_size)
            display.set_address_window(
                window_x,
                window_y,
                window_x + window_size - 1,
                window_y + window_size - 1,
            )
            display.send_command(display.CMD_WRITE_RAM, payload)
        elif step == "full-white":
            if not display.initialized:
                raise RuntimeError("full-white step requires the display to be initialized first")
            payload = bytes([0xFF, 0xFF]) * (display.width * display.height)
            display.write_pixels(payload)
        elif step == "software-reset":
            display.software_reset()
        elif step == "sleep-in":
            display.sleep_in()
        elif step == "sleep-out":
            display.sleep_out()
        elif step == "display-off":
            display.display_off()
        elif step == "display-on":
            display.display_on()
        elif step == "invert-off":
            display.set_inversion(False)
        elif step == "invert-on":
            display.set_inversion(True)
        elif step == "all-pixels-off":
            display.set_all_pixels(False)
        elif step == "all-pixels-on":
            display.set_all_pixels(True)
        elif step == "normal-on":
            display.normal_mode_on()
        else:
            raise ValueError(f"Unknown step: {step}")

        recorder.record("step_complete", step=step)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Saleae-oriented SPI debug harness for the GC9A01 display",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--config", type=Path, default=Path("config/config.yaml"))
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--output-dir", type=Path, default=Path("logs/saleae_spi_debug"))

    parser.add_argument("--spi-bus", type=int)
    parser.add_argument("--spi-device", type=int)
    parser.add_argument("--spi-speed", type=int)
    parser.add_argument("--dc-pin", type=int)
    parser.add_argument("--reset-pin", type=int)
    parser.add_argument("--manual-cs", dest="manual_cs", action="store_true", default=None)
    parser.add_argument("--hardware-cs", dest="manual_cs", action="store_false")
    parser.add_argument(
        "--cs-pin",
        type=_parse_optional_int,
        default=argparse.SUPPRESS,
        help="Panel CS GPIO for manual four-wire framing; defaults to config or inferred SPI CE pin",
    )
    parser.add_argument("--madctl", type=_parse_int)

    parser.add_argument("--step", action="append", choices=STEP_CHOICES)
    parser.add_argument("--probe", action="append", dest="probes", help="Read probe like 0x04:4")
    parser.add_argument("--window-x", type=int, default=0)
    parser.add_argument("--window-y", type=int, default=0)
    parser.add_argument("--window-size", type=int, default=8)

    parser.add_argument("--marker-pin", type=int, default=None, help="GPIO used as a Saleae marker")
    parser.add_argument("--marker-high-ms", type=float, default=5.0)
    parser.add_argument("--marker-low-ms", type=float, default=5.0)
    parser.add_argument(
        "--sync-pulses",
        type=int,
        default=6,
        help="Marker pulses emitted before the first bus activity",
    )

    parser.add_argument(
        "--arm-seconds",
        type=float,
        default=2.0,
        help="Delay before emitting the sync marker in manual capture mode",
    )

    parser.add_argument("--saleae-capture", action="store_true", help="Use Logic 2 automation to capture the run")
    parser.add_argument("--saleae-launch", action="store_true", help="Launch Logic 2 instead of connecting to an existing instance")
    parser.add_argument("--saleae-logic2-path", default=None)
    parser.add_argument("--saleae-port", type=int, default=10430)
    parser.add_argument("--saleae-device-id", default=None)
    parser.add_argument("--saleae-sample-rate", type=int, default=25_000_000)
    parser.add_argument("--saleae-threshold", type=float, default=None)
    parser.add_argument("--saleae-capture-seconds", type=float, default=3.0)
    parser.add_argument("--saleae-trigger", action="store_true", help="Use the marker channel as a digital trigger")

    parser.add_argument("--saleae-sclk-channel", type=int, default=0)
    parser.add_argument("--saleae-mosi-channel", type=int, default=1)
    parser.add_argument("--saleae-miso-channel", type=int, default=None)
    parser.add_argument("--saleae-cs-channel", type=_parse_optional_int, default=2)
    parser.add_argument("--saleae-dc-channel", type=int, default=3)
    parser.add_argument("--saleae-reset-channel", type=int, default=4)
    parser.add_argument("--saleae-marker-channel", type=int, default=5)

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)

    if GPIO is None:
        logger.error("RPi.GPIO not installed. Install via: pip install RPi.GPIO")
        return 1

    display_defaults = _load_display_defaults(args.config)
    output_dir = _resolve_output_dir(args.output_dir)
    recorder = EventRecorder(output_dir)

    steps = _resolve_steps(args.step or [])
    probes = [_parse_probe_spec(spec) for spec in (args.probes or DEFAULT_READ_PROBES)]

    display_kwargs = {
        "spi_bus": args.spi_bus if args.spi_bus is not None else display_defaults.get("spi_bus", 0),
        "spi_device": args.spi_device if args.spi_device is not None else display_defaults.get("spi_device", 0),
        "spi_speed": args.spi_speed if args.spi_speed is not None else display_defaults.get("spi_speed", 10_000_000),
        "dc_pin": args.dc_pin if args.dc_pin is not None else display_defaults.get("spi_dc_pin", 25),
        "reset_pin": args.reset_pin if args.reset_pin is not None else display_defaults.get("spi_reset_pin", 27),
        "manual_cs": args.manual_cs if args.manual_cs is not None else display_defaults.get("spi_manual_cs", True),
        "cs_pin": getattr(args, "cs_pin", display_defaults.get("spi_cs_pin", None)),
        "madctl": args.madctl if args.madctl is not None else display_defaults.get("madctl", GC9A01_SPI.DEFAULT_MADCTL),
    }
    logical_spi_cs_gpio = _infer_logical_spi_cs_gpio(display_kwargs["spi_bus"], display_kwargs["spi_device"])

    marker = MarkerPin(args.marker_pin)
    marker_high_s = args.marker_high_ms / 1000.0
    marker_low_s = args.marker_low_ms / 1000.0

    if logical_spi_cs_gpio is not None:
        logger.info(
            "SPI%d.%d maps to logical hardware CS GPIO%d; panel CS mode is %s",
            display_kwargs["spi_bus"],
            display_kwargs["spi_device"],
            logical_spi_cs_gpio,
            _panel_cs_description(
                display_kwargs["cs_pin"],
                logical_spi_cs_gpio,
                display_kwargs["manual_cs"],
            ),
        )

    analyzer_settings = _saleae_analyzer_settings(
        clock_channel=args.saleae_sclk_channel,
        mosi_channel=args.saleae_mosi_channel,
        miso_channel=args.saleae_miso_channel,
        cs_channel=args.saleae_cs_channel,
    )

    raw_channels = sorted(
        {
            channel
            for channel in [
                args.saleae_sclk_channel,
                args.saleae_mosi_channel,
                args.saleae_miso_channel,
                args.saleae_cs_channel,
                args.saleae_dc_channel,
                args.saleae_reset_channel,
                args.saleae_marker_channel if marker.enabled else None,
            ]
            if channel is not None
        }
    )

    recorder.write_metadata(
        argv=sys.argv,
        output_dir=str(output_dir),
        steps=steps,
        probes=[f"0x{command:02X}:{length}" for command, length in probes],
        display_kwargs=display_kwargs,
        manual_cs=display_kwargs["manual_cs"],
        panel_cs_gpio=display_kwargs["cs_pin"],
        logical_spi_cs_gpio=logical_spi_cs_gpio,
        panel_cs_description=_panel_cs_description(
            display_kwargs["cs_pin"],
            logical_spi_cs_gpio,
            display_kwargs["manual_cs"],
        ),
        marker_pin=args.marker_pin,
        recommended_saleae_channels={
            "sclk": args.saleae_sclk_channel,
            "mosi": args.saleae_mosi_channel,
            "miso": args.saleae_miso_channel,
            "cs": args.saleae_cs_channel,
            "dc": args.saleae_dc_channel,
            "reset": args.saleae_reset_channel,
            "marker": args.saleae_marker_channel if marker.enabled else None,
            "logical_spi_cs_gpio": logical_spi_cs_gpio,
        },
        recommended_spi_analyzer=analyzer_settings,
    )

    (output_dir / "recommended_spi_analyzer.json").write_text(
        json.dumps(analyzer_settings, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    logger.info("Output directory: %s", output_dir)
    logger.info("Display parameters: %s", display_kwargs)
    logger.info("Steps: %s", ", ".join(steps))

    marker.setup()
    marker.cleanup()

    display = SaleaeTracingDisplay(**display_kwargs, recorder=recorder)

    def run_sequence() -> None:
        marker.pulse(args.sync_pulses, marker_high_s, marker_low_s)
        display.connect()
        try:
            _run_steps(
                display=display,
                steps=steps,
                recorder=recorder,
                marker=marker,
                marker_high_s=marker_high_s,
                marker_low_s=marker_low_s,
                read_probes=probes,
                window_x=args.window_x,
                window_y=args.window_y,
                window_size=args.window_size,
            )
        finally:
            display.disconnect()

    try:
        if args.saleae_capture:
            if args.saleae_trigger and not marker.enabled:
                raise RuntimeError("--saleae-trigger requires --marker-pin")

            controller = SaleaeAutomationController(
                output_dir=output_dir,
                enabled_channels=raw_channels,
                digital_sample_rate=args.saleae_sample_rate,
                digital_threshold_volts=args.saleae_threshold,
                port=args.saleae_port,
                device_id=args.saleae_device_id,
                capture_seconds=args.saleae_capture_seconds,
                marker_channel=args.saleae_marker_channel if marker.enabled else None,
                use_trigger=args.saleae_trigger,
                launch_logic2=args.saleae_launch,
                logic2_path=args.saleae_logic2_path,
                recorder=recorder,
            )
            controller.run(
                callback=run_sequence,
                analyzer_settings=analyzer_settings,
                raw_channels=raw_channels,
            )
        else:
            _countdown(args.arm_seconds, "Arm Saleae capture")
            run_sequence()

        recorder.record("run_complete", status="ok")
        logger.info("Saleae SPI debug run complete")
        logger.info("Artifacts written to %s", output_dir)
        return 0

    except Exception as exc:
        recorder.record("run_failed", error=str(exc))
        logger.error("Saleae SPI debug run failed: %s", exc, exc_info=True)
        return 1
    finally:
        try:
            marker.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
