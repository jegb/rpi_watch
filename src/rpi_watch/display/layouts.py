"""Predefined layout templates for GC9A01 display.

Provides common layout patterns combining text, gauges, and progress indicators.
"""

import logging
from typing import Optional, Tuple, Dict, Any
from enum import Enum

from PIL import Image, ImageDraw

from .components import TextRenderer, CircularGauge, ProgressBar, SparklineRenderer, TextSize
from .renderer import MetricRenderer

logger = logging.getLogger(__name__)


class LayoutType(Enum):
    """Predefined layout types."""
    LARGE_METRIC = "large_metric"           # XL metric + subtitle
    METRIC_WITH_GAUGE = "metric_with_gauge" # Metric + circular gauge
    MULTI_RING_GAUGE = "multi_ring_gauge"   # Multi-metric gauge
    TEXT_OVER_GAUGE = "text_over_gauge"     # Text overlaid on gauge
    SPLIT_METRICS = "split_metrics"         # Two metrics side-by-side
    GAUGE_WITH_STATS = "gauge_with_stats"   # Gauge + statistics
    RADIAL_DASHBOARD = "radial_dashboard"   # 3 metrics in triangular layout
    PROGRESS_STACK = "progress_stack"       # Stacked progress bars
    PM_BARS = "pm_bars"                     # PM1/PM2.5/PM4/PM10 stacked bars
    METRIC_RING = "metric_ring"             # Single metric over threshold-colored ring


class ColorScheme(Enum):
    """Predefined color schemes."""
    BRIGHT = {
        "primary": (255, 255, 255),     # White
        "secondary": (200, 200, 200),   # Light gray
        "accent": (0, 255, 0),          # Bright green
        "warning": (255, 165, 0),       # Orange
        "critical": (255, 0, 0),        # Red
        "background": (0, 0, 0),        # Black
    }

    OCEAN = {
        "primary": (100, 200, 255),     # Light blue
        "secondary": (70, 150, 200),    # Medium blue
        "accent": (0, 255, 200),        # Cyan
        "warning": (255, 150, 0),       # Orange
        "critical": (255, 0, 0),        # Red
        "background": (10, 30, 60),     # Dark blue
    }

    FOREST = {
        "primary": (100, 255, 100),     # Light green
        "secondary": (70, 200, 70),     # Medium green
        "accent": (0, 255, 100),        # Bright green
        "warning": (255, 200, 0),       # Yellow
        "critical": (255, 50, 50),      # Red
        "background": (20, 40, 20),     # Dark green
    }

    SUNSET = {
        "primary": (255, 150, 100),     # Coral
        "secondary": (255, 100, 50),    # Orange
        "accent": (255, 200, 0),        # Gold
        "warning": (255, 100, 0),       # Dark orange
        "critical": (200, 0, 0),        # Dark red
        "background": (50, 20, 30),     # Dark purple
    }

    MONOCHROME = {
        "primary": (255, 255, 255),     # White
        "secondary": (180, 180, 180),   # Light gray
        "accent": (128, 128, 128),      # Medium gray
        "warning": (200, 200, 200),     # Light gray
        "critical": (100, 100, 100),    # Dark gray
        "background": (0, 0, 0),        # Black
    }


class DisplayLayout:
    """Base class for display layouts."""

    def __init__(
        self,
        width: int = 240,
        height: int = 240,
        color_scheme: ColorScheme = ColorScheme.BRIGHT,
        font_path: Optional[str] = None,
    ):
        """Initialize layout.

        Args:
            width: Canvas width
            height: Canvas height
            color_scheme: Color scheme to use
        """
        self.width = width
        self.height = height
        self.color_scheme = color_scheme.value
        self.bg_color = self.color_scheme["background"]
        self.font_path = font_path

        self.text_renderer = TextRenderer(width=width, height=height, font_path=font_path)
        self.gauge = CircularGauge(width=width, height=height, font_path=font_path)
        self.progress = ProgressBar(width=width, height=height, font_path=font_path)
        self.sparkline = SparklineRenderer(width=width, height=48)

    def render(self, **kwargs) -> Image.Image:
        """Render layout with given data.

        Args:
            **kwargs: Layout-specific parameters

        Returns:
            PIL Image
        """
        raise NotImplementedError


class LargeMetricLayout(DisplayLayout):
    """Layout: Large metric with title and detail."""

    def render(
        self,
        value: float,
        title: Optional[str] = None,
        detail: Optional[str] = None,
        unit: str = "",
        decimal_places: int = 1,
        value_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Render large metric layout.

        Args:
            value: Main metric value
            title: Title/subtitle text
            detail: Detail text
            unit: Unit label
            decimal_places: Decimal places
            value_color: Custom value color

        Returns:
            PIL Image
        """
        if value_color is None:
            value_color = self.color_scheme["primary"]

        # Format value
        value_text = f"{value:.{decimal_places}f}{unit}"

        return self.text_renderer.render_multiline(
            main_text=value_text,
            sub_text=title,
            detail_text=detail,
            main_color=value_color,
            sub_color=self.color_scheme["secondary"],
            detail_color=self.color_scheme["secondary"],
            background=self.bg_color,
        )


class MetricWithGaugeLayout(DisplayLayout):
    """Layout: Metric text overlaid on circular gauge."""

    def render(
        self,
        value: float,
        min_value: float = 0.0,
        max_value: float = 100.0,
        title: Optional[str] = None,
        unit: str = "",
        gauge_radius: int = 85,
        decimal_places: int = 1,
    ) -> Image.Image:
        """Render metric with gauge background.

        Args:
            value: Metric value
            min_value: Gauge minimum
            max_value: Gauge maximum
            title: Title text
            unit: Unit label
            gauge_radius: Gauge radius
            decimal_places: Decimal places

        Returns:
            PIL Image
        """
        # Create gauge background
        gauge_img = self.gauge.render_gauge(
            value=value,
            min_value=min_value,
            max_value=max_value,
            background_color=self.bg_color,
            gauge_color=self.color_scheme["accent"],
            ring_color=self.color_scheme["secondary"],
            show_value=False,
        )

        # Create text overlay
        value_text = f"{value:.{decimal_places}f}{unit}"
        text_img = self.text_renderer.render_multiline(
            main_text=value_text,
            sub_text=title,
            detail_text=None,
            main_color=self.color_scheme["primary"],
            sub_color=self.color_scheme["secondary"],
            background=self.bg_color,
        )

        # Blend gauge and text (gauge as background, text on top)
        combined = Image.blend(gauge_img, text_img, 0.7)

        logger.debug(f"Rendered metric with gauge: {value}")
        return combined


class MultiRingGaugeLayout(DisplayLayout):
    """Layout: Multiple concentric gauge rings for multiple metrics."""

    def render(
        self,
        values: list,
        labels: Optional[list] = None,
        min_value: float = 0.0,
        max_value: float = 100.0,
        center_text: Optional[str] = None,
    ) -> Image.Image:
        """Render multi-ring gauge.

        Args:
            values: List of metric values
            labels: Optional labels for each ring
            min_value: Gauge minimum
            max_value: Gauge maximum
            center_text: Text to display in center

        Returns:
            PIL Image
        """
        # Create gauge image
        gauge_img = self.gauge.render_multi_ring_gauge(
            values=values,
            min_value=min_value,
            max_value=max_value,
        )

        # Add center text if provided
        if center_text:
            draw = ImageDraw.Draw(gauge_img)
            bbox = draw.textbbox((0, 0), center_text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (self.width - text_width) // 2
            text_y = (self.height - text_height) // 2
            draw.text(
                (text_x, text_y),
                center_text,
                fill=self.color_scheme["primary"],
            )

        logger.debug(f"Rendered multi-ring gauge with {len(values)} rings")
        return gauge_img


class TextOverGaugeLayout(DisplayLayout):
    """Layout: Large text centered over gauge background."""

    def render(
        self,
        main_text: str,
        gauge_value: float = 50.0,
        min_value: float = 0.0,
        max_value: float = 100.0,
        sub_text: Optional[str] = None,
        text_size: TextSize = TextSize.XL,
    ) -> Image.Image:
        """Render text overlaid on gauge.

        Args:
            main_text: Main text to display
            gauge_value: Gauge fill value
            min_value: Gauge minimum
            max_value: Gauge maximum
            sub_text: Optional subtitle
            text_size: Text size

        Returns:
            PIL Image
        """
        # Create gauge
        gauge_img = self.gauge.render_gauge(
            value=gauge_value,
            min_value=min_value,
            max_value=max_value,
            background_color=self.bg_color,
            gauge_color=self.color_scheme["accent"],
            show_value=False,
        )

        # Create text
        text_img = self.text_renderer.render_text(
            main_text,
            size=text_size,
            color=self.color_scheme["primary"],
            background=self.bg_color,
        )

        # Blend
        combined = Image.blend(gauge_img, text_img, 0.75)
        logger.debug(f"Rendered text over gauge: '{main_text}'")
        return combined


class SplitMetricsLayout(DisplayLayout):
    """Layout: Two metrics side-by-side."""

    def render(
        self,
        left_value: float,
        right_value: float,
        left_label: str = "Left",
        right_label: str = "Right",
        left_unit: str = "",
        right_unit: str = "",
        decimal_places: int = 1,
    ) -> Image.Image:
        """Render two metrics side-by-side.

        Args:
            left_value: Left metric value
            right_value: Right metric value
            left_label: Left label
            right_label: Right label
            left_unit: Left unit
            right_unit: Right unit
            decimal_places: Decimal places

        Returns:
            PIL Image
        """
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Left side
        left_text = f"{left_value:.{decimal_places}f}{left_unit}"
        left_bbox = draw.textbbox((0, 0), left_text)
        left_width = left_bbox[2] - left_bbox[0]
        left_x = (self.width // 4) - (left_width // 2)
        left_y = self.height // 3

        draw.text(
            (left_x, left_y),
            left_text,
            fill=self.color_scheme["primary"],
        )

        # Left label
        left_label_bbox = draw.textbbox((0, 0), left_label)
        left_label_width = left_label_bbox[2] - left_label_bbox[0]
        label_x = (self.width // 4) - (left_label_width // 2)
        label_y = left_y + 50

        draw.text(
            (label_x, label_y),
            left_label,
            fill=self.color_scheme["secondary"],
        )

        # Right side
        right_text = f"{right_value:.{decimal_places}f}{right_unit}"
        right_bbox = draw.textbbox((0, 0), right_text)
        right_width = right_bbox[2] - right_bbox[0]
        right_x = (3 * self.width // 4) - (right_width // 2)
        right_y = self.height // 3

        draw.text(
            (right_x, right_y),
            right_text,
            fill=self.color_scheme["primary"],
        )

        # Right label
        right_label_bbox = draw.textbbox((0, 0), right_label)
        right_label_width = right_label_bbox[2] - right_label_bbox[0]
        right_label_x = (3 * self.width // 4) - (right_label_width // 2)
        right_label_y = right_y + 50

        draw.text(
            (right_label_x, right_label_y),
            right_label,
            fill=self.color_scheme["secondary"],
        )

        # Dividing line
        draw.line(
            [(self.width // 2, 20), (self.width // 2, self.height - 20)],
            fill=self.color_scheme["secondary"],
            width=1,
        )

        logger.debug(f"Rendered split metrics: {left_value} | {right_value}")
        return img


class RadialDashboardLayout(DisplayLayout):
    """Layout: Three metrics in radial/triangular arrangement."""

    def render(
        self,
        top_value: float,
        bottom_left_value: float,
        bottom_right_value: float,
        top_label: str = "Top",
        bottom_left_label: str = "BL",
        bottom_right_label: str = "BR",
        decimal_places: int = 1,
    ) -> Image.Image:
        """Render three metrics in radial layout.

        Arrangement:
                 TOP
                /   \\
              BL     BR

        Args:
            top_value: Top metric value
            bottom_left_value: Bottom-left metric value
            bottom_right_value: Bottom-right metric value
            top_label: Top label
            bottom_left_label: Bottom-left label
            bottom_right_label: Bottom-right label
            decimal_places: Decimal places

        Returns:
            PIL Image
        """
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        import math

        center_x = self.width // 2
        center_y = self.height // 2
        radius = 70

        # Positions (top, bottom-left, bottom-right)
        positions = [
            (center_x, center_y - radius, top_value, top_label),  # Top (270°)
            (
                center_x - radius * math.cos(math.radians(30)),  # Bottom-left (210°)
                center_y + radius * math.sin(math.radians(30)),
                bottom_left_value,
                bottom_left_label,
            ),
            (
                center_x + radius * math.cos(math.radians(30)),  # Bottom-right (330°)
                center_y + radius * math.sin(math.radians(30)),
                bottom_right_value,
                bottom_right_label,
            ),
        ]

        value_font = self.text_renderer.get_font(TextSize.SMALL)
        label_font = self.text_renderer.get_font(TextSize.TINY)

        for x, y, value, label in positions:
            value_text = f"{value:.{decimal_places}f}"

            # Draw value
            bbox = draw.textbbox((0, 0), value_text, font=value_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = x - text_width // 2
            text_y = y - text_height // 2

            draw.text(
                (text_x, text_y),
                value_text,
                fill=self.color_scheme["primary"],
                font=value_font,
            )

            # Draw label below
            label_bbox = draw.textbbox((0, 0), label, font=label_font)
            label_width = label_bbox[2] - label_bbox[0]
            label_x = x - label_width // 2
            label_y = y + text_height + 5

            draw.text(
                (label_x, label_y),
                label,
                fill=self.color_scheme["secondary"],
                font=label_font,
            )

            # Draw small circle at position
            circle_radius = 3
            draw.ellipse(
                [(x - circle_radius, y - circle_radius), (x + circle_radius, y + circle_radius)],
                fill=self.color_scheme["accent"],
            )

        # Draw connecting lines from center to positions
        for x, y, _, _ in positions:
            draw.line([(center_x, center_y), (x, y)], fill=self.color_scheme["secondary"], width=1)

        # Draw center circle
        center_circle_radius = 5
        draw.ellipse(
            [
                (center_x - center_circle_radius, center_y - center_circle_radius),
                (center_x + center_circle_radius, center_y + center_circle_radius),
            ],
            fill=self.color_scheme["accent"],
        )

        logger.debug(f"Rendered radial dashboard: {top_value}, {bottom_left_value}, {bottom_right_value}")
        return img


class ProgressStackLayout(DisplayLayout):
    """Layout: Stacked progress bars for multiple metrics."""

    def render(
        self,
        metrics: list,
        max_value: float = 100.0,
        show_labels: bool = True,
    ) -> Image.Image:
        """Render stacked progress bars.

        Args:
            metrics: List of dicts with 'value', 'label', 'color' keys
            max_value: Maximum value for scaling
            show_labels: Show labels next to bars

        Returns:
            PIL Image
        """
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        num_bars = len(metrics)
        bar_height = max(5, (self.height - 20) // num_bars)
        start_y = 10

        font = self.text_renderer.get_font(TextSize.TINY)

        for i, metric in enumerate(metrics):
            value = metric.get("value", 0)
            label = metric.get("label", f"Metric {i+1}")
            color = metric.get("color", self.color_scheme["accent"])

            y = start_y + i * (bar_height + 5)

            # Background bar
            bar_width = self.width - 40 if show_labels else self.width - 20
            bar_x = 20 if show_labels else 10

            draw.rectangle(
                [(bar_x, y), (bar_x + bar_width, y + bar_height)],
                outline=self.color_scheme["secondary"],
                width=1,
            )

            # Filled portion
            percentage = (value / max_value) if max_value > 0 else 0
            filled_width = int(bar_width * percentage)

            if filled_width > 0:
                draw.rectangle(
                    [(bar_x, y), (bar_x + filled_width, y + bar_height)],
                    fill=color,
                )

            # Label
            if show_labels:
                label_text = f"{label}: {value:.0f}"
                draw.text((10, y), label_text, fill=self.color_scheme["secondary"], font=font)

        logger.debug(f"Rendered progress stack with {num_bars} bars")
        return img


class PMBarsLayout(DisplayLayout):
    """Layout: four particulate matter bars with a shared unit label."""

    DEFAULT_FIELDS = (
        ("pm_1_0", "PM1"),
        ("pm_2_5", "PM2.5"),
        ("pm_4_0", "PM4"),
        ("pm_10_0", "PM10"),
    )

    DEFAULT_COLORS = {
        "pm_1_0": (92, 172, 255),
        "pm_2_5": (0, 214, 143),
        "pm_4_0": (255, 195, 0),
        "pm_10_0": (255, 107, 53),
    }

    def render(
        self,
        payload: Dict[str, Any],
        *,
        title: str = "PARTICLES",
        unit_label: str = "µg/m³",
        metric_fields: Optional[list] = None,
        metric_colors: Optional[dict[str, Tuple[int, int, int]]] = None,
        max_value: Optional[float] = None,
        auto_scale_floor: float = 25.0,
    ) -> Image.Image:
        """Render four PM bars from the current payload."""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        field_specs = metric_fields or list(self.DEFAULT_FIELDS)
        normalized_fields: list[tuple[str, str]] = []
        for item in field_specs:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                normalized_fields.append((str(item[0]), str(item[1])))
            else:
                field_name = str(item)
                normalized_fields.append((field_name, field_name.upper()))

        values = []
        for field_name, _ in normalized_fields:
            try:
                values.append(float(payload.get(field_name, 0.0)))
            except (TypeError, ValueError):
                values.append(0.0)

        scale_max = max_value or max(auto_scale_floor, max(values or [auto_scale_floor]))
        colors = {**self.DEFAULT_COLORS, **(metric_colors or {})}

        header_top = 14
        header_height = 22
        footer_height = 16
        content_top = header_top + header_height + 14
        content_bottom = self.height - footer_height - 18
        row_gap = 10
        row_count = max(1, len(normalized_fields))
        row_height = max(20, int((content_bottom - content_top - (row_gap * (row_count - 1))) / row_count))
        label_width = 52
        value_width = 46
        bar_left = 16 + label_width + 8
        bar_right = self.width - 16 - value_width
        bar_width = max(24, bar_right - bar_left)
        bar_height = max(10, row_height - 8)
        bar_radius = max(4, bar_height // 2)

        title_font, title_bbox = self.text_renderer.fit_font(
            title,
            22,
            max_width=self.width - 32,
            min_size=16,
            max_height=header_height,
        )
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((self.width - title_width) // 2, header_top - title_bbox[1]),
            title,
            fill=self.color_scheme["secondary"],
            font=title_font,
        )

        for index, ((field_name, label), value) in enumerate(zip(normalized_fields, values)):
            row_y = content_top + (index * (row_height + row_gap))
            bar_y = row_y + ((row_height - bar_height) // 2)
            row_color = colors.get(field_name, self.color_scheme["accent"])

            label_font, label_bbox = self.text_renderer.fit_font(
                label,
                20,
                max_width=label_width,
                min_size=12,
                max_height=row_height,
            )
            label_width_actual = label_bbox[2] - label_bbox[0]
            label_x = 16 + max(0, (label_width - label_width_actual) // 2)
            draw.text(
                (label_x, row_y - label_bbox[1]),
                label,
                fill=self.color_scheme["secondary"],
                font=label_font,
            )

            value_text = f"{value:.1f}"
            value_font, value_bbox = self.text_renderer.fit_font(
                value_text,
                20,
                max_width=value_width,
                min_size=12,
                max_height=row_height,
            )
            value_width_actual = value_bbox[2] - value_bbox[0]
            value_x = self.width - 16 - value_width_actual
            draw.text(
                (value_x, row_y - value_bbox[1]),
                value_text,
                fill=self.color_scheme["primary"],
                font=value_font,
            )

            draw.rounded_rectangle(
                [(bar_left, bar_y), (bar_left + bar_width, bar_y + bar_height)],
                radius=bar_radius,
                outline=self.color_scheme["secondary"],
                fill=(28, 28, 28),
            )
            fill_width = int(bar_width * max(0.0, min(1.0, value / scale_max)))
            if fill_width > 0:
                draw.rounded_rectangle(
                    [(bar_left, bar_y), (bar_left + fill_width, bar_y + bar_height)],
                    radius=bar_radius,
                    fill=row_color,
                )

        unit_font, unit_bbox = self.text_renderer.fit_font(
            unit_label,
            18,
            max_width=self.width - 32,
            min_size=12,
            max_height=footer_height,
        )
        unit_width = unit_bbox[2] - unit_bbox[0]
        draw.text(
            ((self.width - unit_width) // 2, self.height - footer_height - 8 - unit_bbox[1]),
            unit_label,
            fill=self.color_scheme["secondary"],
            font=unit_font,
        )

        return img


class MetricRingLayout(DisplayLayout):
    """Layout: centered metric value inside a threshold-colored ring."""

    def render(
        self,
        value: float,
        *,
        title: str = "TEMP",
        unit: str = "°C",
        decimal_places: int = 1,
        min_value: float = 0.0,
        max_value: float = 40.0,
        start_angle: float = 135.0,
        end_angle: float = 405.0,
        thickness: int = 16,
        rounded_caps: bool = True,
        thresholds: Optional[list] = None,
        track_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Render a single metric over a configurable ring."""
        track = track_color or self.color_scheme["secondary"]
        img = self.gauge.render_gradient_ring(
            value,
            min_value=min_value,
            max_value=max_value,
            thresholds=thresholds,
            start_angle=start_angle,
            end_angle=end_angle,
            thickness=thickness,
            background_color=self.bg_color,
            track_color=track,
            rounded_caps=rounded_caps,
        )
        draw = ImageDraw.Draw(img)

        value_text = f"{value:.{decimal_places}f}"
        value_color = CircularGauge.color_from_thresholds(
            value,
            thresholds,
            min_value=min_value,
            max_value=max_value,
        )

        inner_margin = max(42, thickness + 28)
        available_width = self.width - (inner_margin * 2)
        available_height = self.height - (inner_margin * 2)

        title_font, title_bbox = self.text_renderer.fit_font(
            title,
            24,
            max_width=available_width,
            min_size=14,
            max_height=max(16, int(available_height * 0.18)),
        )
        unit_font, unit_bbox = self.text_renderer.fit_font(
            unit,
            22,
            max_width=available_width,
            min_size=14,
            max_height=max(16, int(available_height * 0.18)),
        )

        chosen_value_font = None
        chosen_value_bbox = None
        for size in range(96, 25, -2):
            value_font, value_bbox = self.text_renderer.fit_font(
                value_text,
                size,
                max_width=available_width,
                min_size=24,
            )
            total_height = (
                (title_bbox[3] - title_bbox[1])
                + 10
                + (value_bbox[3] - value_bbox[1])
                + 8
                + (unit_bbox[3] - unit_bbox[1])
            )
            if total_height <= available_height:
                chosen_value_font = value_font
                chosen_value_bbox = value_bbox
                break

        if chosen_value_font is None or chosen_value_bbox is None:
            chosen_value_font, chosen_value_bbox = self.text_renderer.fit_font(
                value_text,
                48,
                max_width=available_width,
                min_size=24,
                max_height=available_height,
            )

        title_height = title_bbox[3] - title_bbox[1]
        value_height = chosen_value_bbox[3] - chosen_value_bbox[1]
        unit_height = unit_bbox[3] - unit_bbox[1]
        total_height = title_height + 10 + value_height + 8 + unit_height
        current_y = inner_margin + max(0, (available_height - total_height) // 2)

        for text, font, bbox, color, gap in (
            (title, title_font, title_bbox, self.color_scheme["secondary"], 10),
            (value_text, chosen_value_font, chosen_value_bbox, value_color, 8),
            (unit, unit_font, unit_bbox, self.color_scheme["secondary"], 0),
        ):
            text_width = bbox[2] - bbox[0]
            text_x = (self.width - text_width) // 2
            draw.text(
                (text_x, current_y - bbox[1]),
                text,
                fill=color,
                font=font,
            )
            current_y += (bbox[3] - bbox[1]) + gap

        return img


def get_layout(layout_type: LayoutType, **config) -> DisplayLayout:
    """Factory function to get layout by type.

    Args:
        layout_type: LayoutType enum value
        **config: Additional configuration

    Returns:
        DisplayLayout instance
    """
    layouts = {
        LayoutType.LARGE_METRIC: LargeMetricLayout,
        LayoutType.METRIC_WITH_GAUGE: MetricWithGaugeLayout,
        LayoutType.MULTI_RING_GAUGE: MultiRingGaugeLayout,
        LayoutType.TEXT_OVER_GAUGE: TextOverGaugeLayout,
        LayoutType.SPLIT_METRICS: SplitMetricsLayout,
        LayoutType.RADIAL_DASHBOARD: RadialDashboardLayout,
        LayoutType.PROGRESS_STACK: ProgressStackLayout,
        LayoutType.PM_BARS: PMBarsLayout,
        LayoutType.METRIC_RING: MetricRingLayout,
    }

    layout_class = layouts.get(layout_type)
    if not layout_class:
        raise ValueError(f"Unknown layout type: {layout_type}")

    color_scheme = config.pop("color_scheme", ColorScheme.BRIGHT)
    return layout_class(color_scheme=color_scheme, **config)
