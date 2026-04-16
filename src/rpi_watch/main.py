"""Main entry point for RPi Watch application."""

import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from .display import (
    GC9A01_SPI,
    ColorScheme,
    MetricRenderer,
    MetricRingLayout,
    PMBarsLayout,
)
from .metrics import (
    MetricStore,
    classify_display_band,
    get_guidance_bands,
    get_guidance_display_range,
    serialize_guidance_bands,
)
from .mqtt import MQTTSubscriber
from .utils import setup_logging

logger = logging.getLogger(__name__)

DEFAULT_FIELD_PRIORITY = (
    'pm_1_0',
    'pm_2_5',
    'pm_4_0',
    'pm_10_0',
    'temp',
    'humidity',
)

FIELD_DISPLAY_DEFAULTS = {
    'pm_1_0': {'decimal_places': 1, 'title_label': 'PM1.0', 'unit_label': 'µg/m³'},
    'pm_2_5': {'decimal_places': 1, 'title_label': 'PM2.5', 'unit_label': 'µg/m³'},
    'pm_4_0': {'decimal_places': 1, 'title_label': 'PM4.0', 'unit_label': 'µg/m³'},
    'pm_10_0': {'decimal_places': 1, 'title_label': 'PM10', 'unit_label': 'µg/m³'},
    'temp': {'decimal_places': 1, 'title_label': 'TEMP', 'unit_label': '°C'},
    'humidity': {'decimal_places': 1, 'title_label': 'HUMID', 'unit_label': '%'},
}

FIELD_RING_DEFAULTS = {
    'pm_1_0': {
        'min_value': 0.0,
        'max_value': 25.0,
        'thresholds': [
            {'value': 0.0, 'color': [92, 172, 255]},
            {'value': 6.0, 'color': [0, 214, 143]},
            {'value': 12.0, 'color': [255, 195, 0]},
            {'value': 20.0, 'color': [255, 107, 53]},
        ],
    },
    'pm_4_0': {
        'min_value': 0.0,
        'max_value': 40.0,
        'thresholds': [
            {'value': 0.0, 'color': [92, 172, 255]},
            {'value': 10.0, 'color': [0, 214, 143]},
            {'value': 20.0, 'color': [255, 195, 0]},
            {'value': 30.0, 'color': [255, 107, 53]},
        ],
    },
    'temp': {
        'min_value': 0.0,
        'max_value': 40.0,
        'thresholds': [
            {'value': 0.0, 'color': [64, 128, 255]},
            {'value': 22.0, 'color': [0, 220, 120]},
            {'value': 35.0, 'color': [255, 96, 64]},
        ],
    },
    'humidity': {
        'min_value': 0.0,
        'max_value': 100.0,
        'thresholds': [
            {'value': 0.0, 'color': [92, 172, 255]},
            {'value': 45.0, 'color': [0, 220, 120]},
            {'value': 70.0, 'color': [250, 204, 21]},
            {'value': 85.0, 'color': [255, 96, 64]},
        ],
    },
}


class RPiWatch:
    """Main application controller for RPi Watch."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the RPi Watch application.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config = self._load_config(config_path)
        self.running = False

        # Initialize logging
        setup_logging(
            level=self.config.get('logging', {}).get('level', 'INFO'),
            log_file=self.config.get('logging', {}).get('log_file')
        )

        logger.info("Initializing RPi Watch application")

        # Initialize components
        state_config = self.config.get('state', {})
        self.metric_store = MetricStore(
            history_size=state_config.get('history_size', 50),
            persist_path=state_config.get('cache_path'),
        )
        self.display = None
        self.renderer = None
        self.pm_bars_layout = None
        self.metric_ring_layout = None
        self.mqtt_subscriber = None
        self._rotation_fields: tuple[str, ...] = ()
        self._rotation_index = 0
        self._rotation_last_switch: Optional[float] = None

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def initialize_components(self) -> None:
        """Initialize display, renderer, and MQTT subscriber."""
        try:
            # Initialize display
            display_config = self.config.get('display', {})
            self.display = GC9A01_SPI(
                spi_bus=display_config.get('spi_bus', 0),
                spi_device=display_config.get('spi_device', 0),
                spi_speed=display_config.get('spi_speed', 10000000),
                dc_pin=display_config.get('spi_dc_pin', 25),
                reset_pin=display_config.get('spi_reset_pin', 27),
                cs_pin=display_config.get('spi_cs_pin'),
                manual_cs=display_config.get('spi_manual_cs', True),
                madctl=display_config.get('madctl', GC9A01_SPI.DEFAULT_MADCTL),
            )
            self.display.connect()
            self.display.init_display()

            # Initialize renderer
            metric_config = self.config.get('metric_display', {})
            color_scheme = self._get_color_scheme(metric_config.get('color_scheme'))
            self.renderer = MetricRenderer(
                width=display_config.get('width', 240),
                height=display_config.get('height', 240),
                font_path=metric_config.get('font_path'),
                font_size=metric_config.get('font_size', 80),
                title_font_size=metric_config.get('title_font_size'),
                unit_font_size=metric_config.get('unit_font_size'),
                text_color=tuple(metric_config.get('text_color', [255, 255, 255])),
                background_color=tuple(metric_config.get('background_color', [0, 0, 0])),
                padding=metric_config.get('padding', 18),
                title_gap=metric_config.get('title_gap', 10),
                unit_gap=metric_config.get('unit_gap', 6),
                sparkline_height=metric_config.get('sparkline_height', 32),
                sparkline_gap=metric_config.get('sparkline_gap', 10),
            )
            self.pm_bars_layout = PMBarsLayout(
                width=display_config.get('width', 240),
                height=display_config.get('height', 240),
                color_scheme=color_scheme,
                font_path=metric_config.get('font_path'),
            )
            self.metric_ring_layout = MetricRingLayout(
                width=display_config.get('width', 240),
                height=display_config.get('height', 240),
                color_scheme=color_scheme,
                font_path=metric_config.get('font_path'),
            )

            # Initialize MQTT subscriber
            mqtt_config = self.config.get('mqtt', {})
            self.mqtt_subscriber = MQTTSubscriber(
                broker_host=mqtt_config.get('broker_host', 'localhost'),
                broker_port=mqtt_config.get('broker_port', 1883),
                topic=mqtt_config.get('topic', 'sensor/metric'),
                qos=mqtt_config.get('qos', 1),
                keepalive=mqtt_config.get('keepalive', 60),
                metric_store=self.metric_store,
                json_field=mqtt_config.get('json_field')
            )

            logger.info("All components initialized successfully")

        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            self.cleanup()
            raise

    def _get_metric_display_config(self) -> dict:
        """Return metric display configuration."""
        return self.config.get('metric_display', {})

    @staticmethod
    def _get_color_scheme(color_scheme_name: Optional[str]) -> ColorScheme:
        """Resolve a configured color scheme name to a ``ColorScheme`` enum."""
        if not color_scheme_name:
            return ColorScheme.BRIGHT
        try:
            return ColorScheme[str(color_scheme_name).upper()]
        except KeyError:
            logger.warning("Unknown color scheme '%s'; falling back to BRIGHT", color_scheme_name)
            return ColorScheme.BRIGHT

    @staticmethod
    def _coerce_color(value, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
        """Normalize a configured RGB color to a tuple."""
        try:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                return tuple(int(channel) for channel in value[:3])
        except (TypeError, ValueError):
            pass
        return fallback

    def _get_layout_mode(self) -> str:
        """Return the configured render layout mode."""
        return str(self._get_metric_display_config().get('layout_mode', 'single_metric')).lower()

    def _get_history_tail(
        self,
        field_name: str,
        *,
        limit: Optional[int] = None,
    ) -> list[tuple[float, float]]:
        """Return recent history for a field."""
        history_limit = limit or self._get_metric_display_config().get('sparkline_points', 10)
        return self.metric_store.get_field_history(field_name, limit=history_limit)

    def _get_metric_value_color(
        self,
        field_name: Optional[str],
        payload: Optional[dict],
    ) -> Optional[tuple[int, int, int]]:
        """Return an optional PM guidance color for the displayed value."""
        band = classify_display_band(field_name, payload)
        if band is None:
            return None
        return band.color

    def _get_ring_profile(self, field_name: Optional[str]) -> dict:
        """Resolve ring min/max/threshold profile for a field."""
        metric_config = self._get_metric_display_config()
        profiles = metric_config.get('ring_profiles') or {}
        configured = profiles.get(field_name, {}) if isinstance(profiles, dict) and field_name else {}
        defaults = FIELD_RING_DEFAULTS.get(field_name, {})

        min_value = float(configured.get('min_value', defaults.get('min_value', metric_config.get('ring_min_value', 0.0))))
        max_value = float(configured.get('max_value', defaults.get('max_value', metric_config.get('ring_max_value', 40.0))))
        thresholds = configured.get('thresholds', defaults.get('thresholds', metric_config.get('ring_thresholds')))

        return {
            'min_value': min_value,
            'max_value': max_value,
            'thresholds': thresholds,
        }

    def _get_preferred_metric_field(self) -> Optional[str]:
        """Return the preferred payload field to display."""
        metric_config = self._get_metric_display_config()
        mqtt_config = self.config.get('mqtt', {})
        return metric_config.get('metric_key') or mqtt_config.get('json_field')

    def _get_rotation_fields(self, numeric_payload: dict[str, float]) -> list[str]:
        """Return the configured rotation order filtered to available numeric fields."""
        metric_config = self._get_metric_display_config()
        configured_fields = metric_config.get('rotate_fields')

        if configured_fields:
            ordered_fields = [str(field_name) for field_name in configured_fields]
        else:
            preferred_field = self._get_preferred_metric_field()
            ordered_fields = []
            if preferred_field:
                ordered_fields.append(preferred_field)
            ordered_fields.extend(DEFAULT_FIELD_PRIORITY)
            ordered_fields.extend(str(field_name) for field_name in numeric_payload.keys())

        seen: set[str] = set()
        rotation_fields: list[str] = []
        for field_name in ordered_fields:
            if field_name in numeric_payload and field_name not in seen:
                rotation_fields.append(field_name)
                seen.add(field_name)

        return rotation_fields

    def _select_rotating_field(
        self,
        numeric_payload: dict[str, float],
        *,
        current_time: Optional[float] = None,
    ) -> Optional[str]:
        """Select the current field according to rotation config and timer state."""
        if not numeric_payload:
            return None

        metric_config = self._get_metric_display_config()
        rotate_metrics = bool(metric_config.get('rotate_metrics', False))
        if not rotate_metrics:
            return None

        rotation_fields = self._get_rotation_fields(numeric_payload)
        if not rotation_fields:
            return None

        now = current_time if current_time is not None else time.time()
        interval_seconds = max(0.5, float(metric_config.get('rotate_interval_seconds', 5.0)))

        rotation_fields_tuple = tuple(rotation_fields)
        if rotation_fields_tuple != self._rotation_fields:
            previous_field = None
            if self._rotation_fields and self._rotation_index < len(self._rotation_fields):
                previous_field = self._rotation_fields[self._rotation_index]
            self._rotation_fields = rotation_fields_tuple
            if previous_field and previous_field in rotation_fields:
                self._rotation_index = rotation_fields.index(previous_field)
            else:
                self._rotation_index = 0
            self._rotation_last_switch = now
            logger.info("Metric rotation fields: %s", ", ".join(rotation_fields))
        elif len(rotation_fields) > 1 and self._rotation_last_switch is not None:
            elapsed = now - self._rotation_last_switch
            if elapsed >= interval_seconds:
                steps = int(elapsed // interval_seconds)
                self._rotation_index = (self._rotation_index + max(1, steps)) % len(rotation_fields)
                self._rotation_last_switch = now
                logger.info("Rotating metric display to %s", rotation_fields[self._rotation_index])
        elif self._rotation_last_switch is None:
            self._rotation_last_switch = now

        return rotation_fields[self._rotation_index]

    def _get_display_metadata(self, field_name: Optional[str]) -> dict:
        """Resolve display labels for a metric field."""
        metric_config = self._get_metric_display_config()
        preferred_field = self._get_preferred_metric_field()
        field_name = field_name or preferred_field
        display_defaults = FIELD_DISPLAY_DEFAULTS.get(field_name, {})
        is_preferred_field = field_name == preferred_field

        if is_preferred_field:
            title_label = metric_config.get(
                'title_label',
                display_defaults.get('title_label', field_name or ''),
            )
            unit_label = metric_config.get(
                'unit_label',
                display_defaults.get('unit_label', ''),
            )
        else:
            title_label = display_defaults.get(
                'title_label',
                metric_config.get('title_label', field_name or ''),
            )
            unit_label = display_defaults.get(
                'unit_label',
                metric_config.get('unit_label', ''),
            )

        return {
            'field': field_name,
            'title_label': title_label,
            'unit_label': unit_label,
            'decimal_places': metric_config.get(
                'decimal_places',
                display_defaults.get('decimal_places', 1),
            ),
        }

    def _get_placeholder_metric(self) -> Optional[dict]:
        """Return placeholder display settings when no reading is available."""
        metric_config = self._get_metric_display_config()
        placeholder_text = metric_config.get('placeholder_text', '--.-')

        if metric_config.get('show_placeholder', True) is False:
            return None

        preferred_field = self._get_preferred_metric_field()
        display_metadata = self._get_display_metadata(preferred_field)
        return {
            'text': str(placeholder_text),
            'title_label': metric_config.get(
                'placeholder_title_label',
                display_metadata.get('title_label', ''),
            ),
            'unit_label': metric_config.get(
                'placeholder_unit_label',
                display_metadata.get('unit_label', ''),
            ),
        }

    def _display_metric_value(
        self,
        value: float | str,
        decimal_places: int,
        title_label: str,
        unit_label: str,
        sparkline_values: Optional[list[tuple[float, float]]] = None,
        value_color: Optional[tuple[int, int, int]] = None,
    ) -> None:
        """Render and display a metric or placeholder."""
        metric_config = self._get_metric_display_config()
        image = self.renderer.render_and_mask(
            value,
            decimal_places=decimal_places,
            title_label=title_label,
            unit_label=unit_label,
            sparkline_values=sparkline_values if metric_config.get('show_sparkline', True) else None,
            sparkline_color=self._coerce_color(
                metric_config.get('sparkline_line_color'),
                tuple(metric_config.get('text_color', [255, 255, 255])),
            ),
            value_color=value_color,
            label_color=tuple(metric_config.get('text_color', [255, 255, 255])),
        )
        self.display.display(image)

    def _display_pm_bars(self, payload: dict) -> None:
        """Render the dedicated PM bars layout."""
        metric_config = self._get_metric_display_config()
        image = self.pm_bars_layout.render(
            payload,
            title=str(metric_config.get('pm_bars_title', 'PM')),
            unit_label=str(metric_config.get('pm_bars_unit_label', 'µg/m³')),
            metric_fields=metric_config.get(
                'pm_bar_fields',
                ['pm_1_0', 'pm_2_5', 'pm_4_0', 'pm_10_0'],
            ),
            metric_colors={
                key: self._coerce_color(value, self.pm_bars_layout.DEFAULT_COLORS.get(key, (255, 255, 255)))
                for key, value in (metric_config.get('pm_bars_colors', {}) or {}).items()
            },
            max_value=metric_config.get('pm_bars_max_value'),
            auto_scale_floor=float(metric_config.get('pm_bars_auto_scale_floor', 25.0)),
            orientation=str(metric_config.get('pm_bars_orientation', 'vertical')),
            bar_gap=int(metric_config.get('pm_bars_gap', 6)),
            scale_padding_ratio=float(metric_config.get('pm_bars_scale_padding_ratio', 0.18)),
        )
        self.display.display(self.renderer.apply_circular_mask(image))

    def _select_ring_metric(
        self,
        payload: Optional[dict],
        scalar_value: Optional[float],
        *,
        current_time: Optional[float] = None,
    ) -> Optional[dict]:
        """Choose which metric should drive the ring layout."""
        metric_config = self._get_metric_display_config()
        numeric_payload = self.metric_store.extract_numeric_payload(payload)
        preferred_field = metric_config.get('ring_field') or self._get_preferred_metric_field()

        if numeric_payload:
            field_name = self._select_rotating_field(
                numeric_payload,
                current_time=current_time,
            )
            if field_name is None:
                if preferred_field and preferred_field in numeric_payload:
                    field_name = preferred_field
                else:
                    selected = self._select_display_metric(payload, current_time=current_time)
                    if selected is None:
                        return None
                    field_name = selected['field']
            value = numeric_payload.get(field_name)
            if value is None:
                return None
        elif scalar_value is not None:
            field_name = preferred_field or self._get_preferred_metric_field() or 'value'
            value = scalar_value
        else:
            return None

        display_metadata = self._get_display_metadata(field_name)
        guidance_bands = get_guidance_bands(field_name)
        guidance_range = get_guidance_display_range(field_name)
        ring_profile = self._get_ring_profile(field_name)
        return {
            'field': field_name,
            'value': value,
            'decimal_places': display_metadata['decimal_places'],
            'title_label': display_metadata['title_label'],
            'unit_label': display_metadata['unit_label'],
            'value_color': self._get_metric_value_color(field_name, payload) if guidance_bands else None,
            'guidance_bands': serialize_guidance_bands(field_name) if guidance_bands else None,
            'guidance_range': guidance_range,
            'ring_min_value': ring_profile['min_value'],
            'ring_max_value': ring_profile['max_value'],
            'thresholds': ring_profile['thresholds'],
        }

    def _display_metric_ring(self, metric: dict) -> None:
        """Render a threshold-colored ring layout."""
        metric_config = self._get_metric_display_config()
        guidance_range = metric.get('guidance_range')
        ring_min_value = guidance_range[0] if guidance_range is not None else float(metric.get('ring_min_value', metric_config.get('ring_min_value', 0.0)))
        ring_max_value = guidance_range[1] if guidance_range is not None else float(metric.get('ring_max_value', metric_config.get('ring_max_value', 40.0)))
        image = self.metric_ring_layout.render(
            metric['value'],
            title=metric['title_label'],
            unit=metric['unit_label'],
            decimal_places=metric['decimal_places'],
            min_value=ring_min_value,
            max_value=ring_max_value,
            start_angle=float(metric_config.get('ring_start_angle', 135.0)),
            end_angle=float(metric_config.get('ring_end_angle', 405.0)),
            thickness=int(metric_config.get('ring_thickness', 20)),
            rounded_caps=bool(metric_config.get('ring_rounded_caps', True)),
            thresholds=metric.get('thresholds', metric_config.get('ring_thresholds')),
            threshold_bands=metric.get('guidance_bands'),
            track_color=self._coerce_color(
                metric_config.get('ring_track_color'),
                self.metric_ring_layout.color_scheme["secondary"],
            ),
            value_color=metric.get('value_color'),
            show_marker=True,
            inner_margin=int(metric_config.get('ring_inner_margin', 54)),
            title_font_size=int(metric_config.get('ring_title_font_size', 20)),
            value_font_size=int(metric_config.get('ring_value_font_size', 82)),
            unit_font_size=int(metric_config.get('ring_unit_font_size', 18)),
            title_gap=int(metric_config.get('ring_title_gap', 8)),
            unit_gap=int(metric_config.get('ring_unit_gap', 6)),
        )
        self.display.display(self.renderer.apply_circular_mask(image))

    def _select_display_metric(
        self,
        payload: Optional[dict],
        *,
        current_time: Optional[float] = None,
    ) -> Optional[dict]:
        """Choose which field from the latest payload should be displayed."""
        if not payload:
            return None

        numeric_payload = self.metric_store.extract_numeric_payload(payload)
        if not numeric_payload:
            return None

        preferred_field = self._get_preferred_metric_field()

        field_name = self._select_rotating_field(
            numeric_payload,
            current_time=current_time,
        )
        if field_name is None:
            if preferred_field and preferred_field in numeric_payload:
                field_name = preferred_field
            else:
                for candidate in DEFAULT_FIELD_PRIORITY:
                    if candidate in numeric_payload:
                        field_name = candidate
                        break

        if field_name is None:
            field_name = next(iter(numeric_payload))

        display_metadata = self._get_display_metadata(field_name)

        return {
            'field': field_name,
            'value': numeric_payload[field_name],
            'decimal_places': display_metadata['decimal_places'],
            'title_label': display_metadata['title_label'],
            'unit_label': display_metadata['unit_label'],
            'value_color': self._get_metric_value_color(field_name, payload),
        }

    def run(self) -> None:
        """Run the main event loop.

        Continuously reads metrics from metric_store and updates the display.
        """
        if self.display is None or self.renderer is None or self.mqtt_subscriber is None:
            raise RuntimeError("Components not initialized. Call initialize_components() first.")

        try:
            logger.info("Starting main event loop")
            self.running = True

            # Start MQTT subscriber (optional - app works offline if broker unavailable)
            try:
                logger.info("Attempting to connect to MQTT broker...")
                self.mqtt_subscriber.start()
                logger.info("✓ MQTT subscriber started")
            except TimeoutError:
                logger.warning("⚠ MQTT broker timeout - running in offline mode")
                logger.warning("  App will display metrics if manually updated")
                logger.warning(
                    f"  To use MQTT: verify broker is running at "
                    f"{self.mqtt_subscriber.broker_host}:{self.mqtt_subscriber.broker_port}"
                )
            except Exception as e:
                logger.warning(f"⚠ Failed to connect to MQTT broker: {e}")
                logger.warning("  Running in offline mode - display ready for test data")

            # Get configuration
            display_config = self.config.get('display', {})
            metric_config = self._get_metric_display_config()
            placeholder_metric = self._get_placeholder_metric()
            refresh_rate = display_config.get('refresh_rate_hz', 2)
            frame_time = 1.0 / refresh_rate

            # Main event loop
            frame_count = 0
            last_render_state = None

            while self.running:
                try:
                    loop_time = time.time()
                    current_payload = self.metric_store.get_payload()
                    current_value = self.metric_store.get_latest()
                    layout_mode = self._get_layout_mode()
                    selected_metric = None

                    if layout_mode == 'pm_bars':
                        if current_payload:
                            pm_snapshot = tuple(
                                self.metric_store.get_field(field_name) or 0.0
                                for field_name in ('pm_1_0', 'pm_2_5', 'pm_4_0', 'pm_10_0')
                            )
                            render_state = ('pm_bars', pm_snapshot)

                            if render_state != last_render_state:
                                self._display_pm_bars(current_payload)
                                last_render_state = render_state
                                frame_count += 1
                                logger.debug("Display updated (frame %s): pm_bars=%s", frame_count, pm_snapshot)
                        elif placeholder_metric is not None:
                            render_state = (
                                'placeholder',
                                placeholder_metric['text'],
                                placeholder_metric['title_label'],
                                placeholder_metric['unit_label'],
                            )

                            if render_state != last_render_state:
                                logger.info(
                                    "Displaying placeholder metric until first MQTT update: %s",
                                    placeholder_metric['text'],
                                )
                                self._display_metric_value(
                                    placeholder_metric['text'],
                                    decimal_places=metric_config.get('decimal_places', 1),
                                    title_label=placeholder_metric['title_label'],
                                    unit_label=placeholder_metric['unit_label'],
                                )
                                last_render_state = render_state
                        else:
                            render_state = ('waiting',)
                            if render_state != last_render_state:
                                logger.info("Waiting for MQTT metric...")
                                self._display_waiting()
                                last_render_state = render_state

                    elif layout_mode == 'metric_ring':
                        ring_metric = self._select_ring_metric(
                            current_payload,
                            current_value,
                            current_time=loop_time,
                        )

                        if ring_metric is not None:
                            render_state = (
                                'metric_ring',
                                ring_metric['field'],
                                ring_metric['value'],
                                ring_metric['decimal_places'],
                                ring_metric['title_label'],
                                ring_metric['unit_label'],
                                ring_metric.get('value_color'),
                            )

                            if render_state != last_render_state:
                                self._display_metric_ring(ring_metric)
                                last_render_state = render_state
                                frame_count += 1
                                logger.debug(
                                    "Display updated (frame %s): ring %s=%s",
                                    frame_count,
                                    ring_metric['field'],
                                    ring_metric['value'],
                                )
                        elif placeholder_metric is not None:
                            render_state = (
                                'placeholder',
                                placeholder_metric['text'],
                                placeholder_metric['title_label'],
                                placeholder_metric['unit_label'],
                            )

                            if render_state != last_render_state:
                                logger.info(
                                    "Displaying placeholder metric until first MQTT update: %s",
                                    placeholder_metric['text'],
                                )
                                self._display_metric_value(
                                    placeholder_metric['text'],
                                    decimal_places=metric_config.get('decimal_places', 1),
                                    title_label=placeholder_metric['title_label'],
                                    unit_label=placeholder_metric['unit_label'],
                                )
                                last_render_state = render_state
                    else:
                        selected_metric = self._select_display_metric(
                            current_payload,
                            current_time=loop_time,
                        )
                        if selected_metric is not None:
                            sparkline_series = self._get_history_tail(selected_metric['field'])
                            sparkline_state = tuple(round(value, 3) for _, value in sparkline_series)
                            render_state = (
                                'metric',
                                selected_metric['field'],
                                selected_metric['value'],
                                selected_metric['decimal_places'],
                                selected_metric['title_label'],
                                selected_metric['unit_label'],
                                selected_metric.get('value_color'),
                                sparkline_state,
                            )

                            # Only update display if value changed (reduces SPI traffic)
                            if render_state != last_render_state:
                                self._display_metric_value(
                                    selected_metric['value'],
                                    decimal_places=selected_metric['decimal_places'],
                                    title_label=selected_metric['title_label'],
                                    unit_label=selected_metric['unit_label'],
                                    sparkline_values=sparkline_series,
                                    value_color=selected_metric.get('value_color'),
                                )
                                last_render_state = render_state
                                frame_count += 1
                                logger.debug(
                                    f"Display updated (frame {frame_count}): "
                                    f"{selected_metric['field']}={selected_metric['value']}"
                                )
                        elif current_value is not None:
                            display_metadata = self._get_display_metadata(self._get_preferred_metric_field())
                            sparkline_field = display_metadata['field'] or self._get_preferred_metric_field() or 'value'
                            sparkline_series = self._get_history_tail(sparkline_field)
                            sparkline_state = tuple(round(value, 3) for _, value in sparkline_series)
                            render_state = (
                                'scalar',
                                current_value,
                                display_metadata['decimal_places'],
                                display_metadata['title_label'],
                                display_metadata['unit_label'],
                                self._get_metric_value_color(display_metadata['field'], current_payload),
                                sparkline_state,
                            )

                            if render_state != last_render_state:
                                self._display_metric_value(
                                    current_value,
                                    decimal_places=display_metadata['decimal_places'],
                                    title_label=display_metadata['title_label'],
                                    unit_label=display_metadata['unit_label'],
                                    sparkline_values=sparkline_series,
                                    value_color=self._get_metric_value_color(display_metadata['field'], current_payload),
                                )
                                last_render_state = render_state
                                frame_count += 1
                                logger.debug(f"Display updated (frame {frame_count}): {current_value}")
                        elif placeholder_metric is not None:
                            render_state = (
                                'placeholder',
                                placeholder_metric['text'],
                                placeholder_metric['title_label'],
                                placeholder_metric['unit_label'],
                            )

                            if render_state != last_render_state:
                                logger.info(
                                    "Displaying placeholder metric until first MQTT update: %s",
                                    placeholder_metric['text'],
                                )
                                self._display_metric_value(
                                    placeholder_metric['text'],
                                    decimal_places=metric_config.get('decimal_places', 1),
                                    title_label=placeholder_metric['title_label'],
                                    unit_label=placeholder_metric['unit_label'],
                                )
                                last_render_state = render_state
                        else:
                            render_state = ('waiting',)
                            if render_state != last_render_state:
                                logger.info("Waiting for MQTT metric...")
                                self._display_waiting()
                                last_render_state = render_state

                    # Sleep for frame time
                    time.sleep(frame_time)

                except Exception as e:
                    logger.error(f"Error in event loop: {e}")
                    # Continue running despite errors
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.cleanup()

    def _display_waiting(self) -> None:
        """Display a "waiting" message on the screen."""
        try:
            placeholder_metric = self._get_placeholder_metric() or {}
            image = self.renderer.render_and_mask(
                "--.-",
                decimal_places=1,
                title_label=placeholder_metric.get('title_label', ''),
                unit_label=placeholder_metric.get(
                    'unit_label',
                    self._get_metric_display_config().get('unit_label', ''),
                ),
            )
            self.display.display(image)
        except Exception as e:
            logger.warning(f"Failed to display waiting message: {e}")

    def cleanup(self) -> None:
        """Clean up resources and shut down gracefully."""
        logger.info("Cleaning up resources...")
        self.running = False

        if self.mqtt_subscriber:
            try:
                self.mqtt_subscriber.stop()
            except Exception as e:
                logger.warning(f"Error stopping MQTT subscriber: {e}")

        if self.display:
            try:
                self.display.disconnect()
            except Exception as e:
                logger.warning(f"Error closing display: {e}")

        logger.info("Cleanup complete")

    def handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.running = False


def main():
    """Main entry point for the application."""
    try:
        # Determine config path
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

        # Create application
        app = RPiWatch(str(config_path))

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, app.handle_signal)
        signal.signal(signal.SIGTERM, app.handle_signal)

        # Initialize and run
        app.initialize_components()
        app.run()

    except Exception as e:
        logger.error(f"Application failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
