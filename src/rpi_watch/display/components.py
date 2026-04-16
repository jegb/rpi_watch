"""UI Components library for GC9A01 display.

Provides reusable components for rendering:
- Text with multiple sizes (XL, Large, Normal, Small)
- Circular gauge with concentric rings
- Progress indicators
"""

import logging
import math
from typing import Any, Optional, Sequence, Tuple
from enum import Enum

from PIL import Image, ImageDraw, ImageFont

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    RESAMPLE_LANCZOS = Image.LANCZOS

from .fonts import load_font

logger = logging.getLogger(__name__)


class TextSize(Enum):
    """Text size presets."""
    XL = 96        # Extra Large (96pt)
    LARGE = 64     # Large (64pt)
    NORMAL = 48    # Normal (48pt)
    SMALL = 32     # Small (32pt)
    TINY = 20      # Tiny (20pt)


class TextAlignment(Enum):
    """Text alignment options."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class TextRenderer:
    """Renders text at various sizes with alignment and styling."""

    def __init__(
        self,
        width: int = 240,
        height: int = 240,
        font_path: Optional[str] = None,
        default_font_size: int = 48,
    ):
        """Initialize text renderer.

        Args:
            width: Canvas width
            height: Canvas height
            font_path: Path to TrueType font
            default_font_size: Default font size in points
        """
        self.width = width
        self.height = height
        self.default_font_size = default_font_size
        self.font_path = font_path
        self.resolved_font_source = None

        # Load font with fallback
        self.font = self._load_font(font_path, default_font_size)
        self.fonts = {}  # Cache for different sizes

        logger.info(
            f"TextRenderer initialized: {width}x{height}, "
            f"font_path={font_path}, resolved_font={self.resolved_font_source}"
        )

    def _load_font(self, font_path: Optional[str], font_size: int) -> ImageFont.FreeTypeFont:
        """Load TrueType font with fallback."""
        font, resolved_source, _ = load_font(font_path, font_size)
        if resolved_source and self.resolved_font_source is None:
            self.resolved_font_source = resolved_source
        return font

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get or load font at specific size."""
        if size not in self.fonts:
            self.fonts[size] = self._load_font(self.font_path, size)
        return self.fonts[size]

    def measure_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
    ) -> tuple[tuple[int, int, int, int], int, int]:
        """Measure text using a temporary drawing context."""
        img = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox, bbox[2] - bbox[0], bbox[3] - bbox[1]

    def fit_font(
        self,
        text: str,
        base_size: int,
        *,
        max_width: int,
        min_size: int = 12,
        max_height: Optional[int] = None,
    ) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
        """Shrink a font until the text fits the target bounds."""
        for size in range(base_size, max(min_size, 1) - 1, -2):
            font = self._get_font(size)
            bbox, text_width, text_height = self.measure_text(text, font)
            if text_width <= max_width and (max_height is None or text_height <= max_height):
                return font, bbox

        font = self._get_font(max(min_size, 1))
        bbox, _, _ = self.measure_text(text, font)
        return font, bbox

    def get_font(self, size: int | TextSize) -> ImageFont.FreeTypeFont:
        """Get a font for a requested size or preset."""
        if isinstance(size, TextSize):
            return self._get_font(size.value)
        return self._get_font(size)

    def render_text(
        self,
        text: str,
        size: TextSize = TextSize.NORMAL,
        color: Tuple[int, int, int] = (255, 255, 255),
        background: Optional[Tuple[int, int, int]] = None,
        alignment: TextAlignment = TextAlignment.CENTER,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> Image.Image:
        """Render text at specified size.

        Args:
            text: Text to render
            size: Text size (from TextSize enum)
            color: RGB text color
            background: Optional RGB background color
            alignment: Text alignment
            x: Optional X position (overrides alignment)
            y: Optional Y position

        Returns:
            PIL Image with rendered text
        """
        font_size = size.value
        font = self._get_font(font_size)

        # Create image
        bg_color = background if background else (0, 0, 0)
        img = Image.new('RGB', (self.width, self.height), bg_color)
        draw = ImageDraw.Draw(img)

        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Calculate position
        if x is None:
            if alignment == TextAlignment.CENTER:
                x = (self.width - text_width) // 2
            elif alignment == TextAlignment.LEFT:
                x = 10
            else:  # RIGHT
                x = self.width - text_width - 10

        if y is None:
            y = (self.height - text_height) // 2

        # Draw text
        draw.text((x, y), text, fill=color, font=font)

        logger.debug(f"Rendered text: '{text}' at {size.name} ({font_size}pt)")
        return img

    def render_multiline(
        self,
        main_text: str,
        sub_text: Optional[str] = None,
        detail_text: Optional[str] = None,
        main_color: Tuple[int, int, int] = (255, 255, 255),
        sub_color: Tuple[int, int, int] = (200, 200, 200),
        detail_color: Tuple[int, int, int] = (150, 150, 150),
        background: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Render multi-level text (main, subtitle, detail).

        Layout:
        ┌─────────────────────┐
        │    MAIN TEXT XL     │  (main_text at XL size)
        │                     │
        │      sub text       │  (sub_text at NORMAL size)
        │   detail info       │  (detail_text at SMALL size)
        └─────────────────────┘

        Args:
            main_text: Primary text (XL size)
            sub_text: Secondary text (NORMAL size)
            detail_text: Detail text (SMALL size)
            main_color: Main text RGB color
            sub_color: Subtitle RGB color
            detail_color: Detail RGB color
            background: Background RGB color

        Returns:
            PIL Image with multi-level text layout
        """
        bg_color = background if background else (0, 0, 0)
        img = Image.new('RGB', (self.width, self.height), bg_color)
        draw = ImageDraw.Draw(img)

        # Main text (XL)
        main_font = self._get_font(TextSize.XL.value)
        main_bbox = draw.textbbox((0, 0), main_text, font=main_font)
        main_width = main_bbox[2] - main_bbox[0]
        main_height = main_bbox[3] - main_bbox[1]
        main_x = (self.width - main_width) // 2
        main_y = 30
        draw.text((main_x, main_y), main_text, fill=main_color, font=main_font)

        # Subtitle (NORMAL)
        if sub_text:
            sub_font = self._get_font(TextSize.NORMAL.value)
            sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
            sub_width = sub_bbox[2] - sub_bbox[0]
            sub_height = sub_bbox[3] - sub_bbox[1]
            sub_x = (self.width - sub_width) // 2
            sub_y = main_y + main_height + 20
            draw.text((sub_x, sub_y), sub_text, fill=sub_color, font=sub_font)

            next_y = sub_y + sub_height
        else:
            next_y = main_y + main_height + 20

        # Detail text (SMALL)
        if detail_text:
            detail_font = self._get_font(TextSize.SMALL.value)
            detail_bbox = draw.textbbox((0, 0), detail_text, font=detail_font)
            detail_width = detail_bbox[2] - detail_bbox[0]
            detail_x = (self.width - detail_width) // 2
            detail_y = next_y + 15
            draw.text((detail_x, detail_y), detail_text, fill=detail_color, font=detail_font)

        logger.debug(f"Rendered multiline text: '{main_text}'")
        return img


class SparklineRenderer:
    """Renders a compact sparkline for recent metric history."""

    def __init__(
        self,
        width: int = 240,
        height: int = 40,
        padding: int = 4,
    ):
        self.width = width
        self.height = height
        self.padding = padding

    @staticmethod
    def _normalize_values(series: Sequence[Any]) -> list[float]:
        """Normalize either raw values or ``(timestamp, value)`` pairs."""
        values: list[float] = []
        for item in series:
            if isinstance(item, tuple) and len(item) >= 2:
                value = item[1]
            else:
                value = item
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        return values

    def render(
        self,
        series: Sequence[Any],
        *,
        background_color: Tuple[int, int, int] = (0, 0, 0),
        line_color: Tuple[int, int, int] = (255, 255, 255),
        fill_color: Optional[Tuple[int, int, int]] = None,
        stroke_width: int = 2,
        point_radius: int = 3,
    ) -> Image.Image:
        """Render a sparkline image from the supplied history."""
        img = Image.new('RGB', (self.width, self.height), background_color)
        draw = ImageDraw.Draw(img)

        values = self._normalize_values(series)
        if not values:
            return img

        if len(values) == 1:
            x = self.width // 2
            y = self.height // 2
            draw.ellipse(
                [
                    (x - point_radius, y - point_radius),
                    (x + point_radius, y + point_radius),
                ],
                fill=line_color,
            )
            return img

        min_value = min(values)
        max_value = max(values)
        value_range = max_value - min_value
        usable_width = max(1, self.width - (self.padding * 2))
        usable_height = max(1, self.height - (self.padding * 2))
        base_y = self.height - self.padding - 1

        points: list[tuple[float, float]] = []
        for index, value in enumerate(values):
            ratio_x = index / max(1, len(values) - 1)
            x = self.padding + (usable_width * ratio_x)
            if value_range == 0:
                y = self.padding + (usable_height / 2)
            else:
                ratio_y = (value - min_value) / value_range
                y = self.padding + usable_height - (usable_height * ratio_y)
            points.append((x, y))

        if fill_color and len(points) >= 2:
            polygon = [(points[0][0], base_y)] + points + [(points[-1][0], base_y)]
            draw.polygon(polygon, fill=fill_color)

        draw.line(points, fill=line_color, width=stroke_width)

        marker_inner_color = tuple(
            max(0, min(255, int((channel * 0.72) + (background * 0.28))))
            for channel, background in zip(line_color, background_color)
        )

        # Mark every sample so short tails remain readable even when the trend is flat.
        for point_index, (x, y) in enumerate(points):
            radius = point_radius + 1 if point_index == len(points) - 1 else point_radius
            draw.ellipse(
                [
                    (x - radius, y - radius),
                    (x + radius, y + radius),
                ],
                fill=background_color,
                outline=line_color,
                width=1,
            )
            draw.ellipse(
                [
                    (x - max(1, radius - 1), y - max(1, radius - 1)),
                    (x + max(1, radius - 1), y + max(1, radius - 1)),
                ],
                fill=marker_inner_color,
            )

        return img


class CircularGauge:
    """Renders circular gauge with concentric rings and needle."""

    def __init__(
        self,
        width: int = 240,
        height: int = 240,
        center_x: Optional[int] = None,
        center_y: Optional[int] = None,
        outer_radius: int = 110,
        font_path: Optional[str] = None,
        value_font_size: int = 28,
    ):
        """Initialize circular gauge.

        Args:
            width: Canvas width
            height: Canvas height
            center_x: Center X coordinate (defaults to width/2)
            center_y: Center Y coordinate (defaults to height/2)
            outer_radius: Outer radius of gauge in pixels
        """
        self.width = width
        self.height = height
        self.center_x = center_x if center_x else width // 2
        self.center_y = center_y if center_y else height // 2
        self.outer_radius = outer_radius
        self.font_path = font_path
        self.value_font_size = value_font_size
        self._font_cache = {}

        logger.info(f"CircularGauge initialized: {width}x{height}, radius={outer_radius}")

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get or load a gauge label font."""
        if size not in self._font_cache:
            font, _, _ = load_font(self.font_path, size)
            self._font_cache[size] = font
        return self._font_cache[size]

    def render_gauge(
        self,
        value: float,
        min_value: float = 0.0,
        max_value: float = 100.0,
        background_color: Tuple[int, int, int] = (0, 0, 0),
        gauge_color: Tuple[int, int, int] = (0, 255, 0),
        ring_color: Tuple[int, int, int] = (100, 100, 100),
        needle_color: Tuple[int, int, int] = (255, 0, 0),
        show_value: bool = True,
        value_text_color: Tuple[int, int, int] = (255, 255, 255),
    ) -> Image.Image:
        """Render circular gauge with value indicator.

        Gauge layout:
        - Outer ring (gray): Shows min/max range
        - Colored arc: Shows current value position
        - Needle: Points to current value
        - Center display: Shows numeric value

        Args:
            value: Current value
            min_value: Minimum value (0° position)
            max_value: Maximum value (360° position)
            background_color: Background RGB color
            gauge_color: Gauge arc RGB color
            ring_color: Background ring RGB color
            needle_color: Needle RGB color
            show_value: Whether to show numeric value
            value_text_color: Numeric value text RGB color

        Returns:
            PIL Image with circular gauge
        """
        # Create base image
        img = Image.new('RGB', (self.width, self.height), background_color)
        draw = ImageDraw.Draw(img)

        # Draw background ring
        ring_radius = self.outer_radius - 5
        self._draw_ring(
            draw,
            center_x=self.center_x,
            center_y=self.center_y,
            radius=ring_radius,
            color=ring_color,
            width=2,
        )

        # Calculate angle for current value (0-360 degrees)
        value_range = max_value - min_value
        if value_range == 0:
            percentage = 0.0
        else:
            percentage = (value - min_value) / value_range
        angle = percentage * 360.0  # 0° = right, 90° = down, 180° = left, 270° = up

        # Draw gauge arc (from 0° to current value)
        self._draw_gauge_arc(
            draw,
            center_x=self.center_x,
            center_y=self.center_y,
            radius=ring_radius,
            angle_end=angle,
            color=gauge_color,
            width=8,
        )

        # Draw needle pointing to current value
        self._draw_needle(
            draw,
            center_x=self.center_x,
            center_y=self.center_y,
            radius=ring_radius - 10,
            angle=angle,
            color=needle_color,
            width=3,
        )

        # Draw center circle
        center_radius = 10
        draw.ellipse(
            [
                (self.center_x - center_radius, self.center_y - center_radius),
                (self.center_x + center_radius, self.center_y + center_radius),
            ],
            fill=needle_color,
        )

        # Show value text in center
        if show_value:
            value_text = f"{value:.1f}"
            font = self._get_font(self.value_font_size)
            bbox = draw.textbbox((0, 0), value_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = self.center_x - text_width // 2
            text_y = self.center_y - text_height // 2
            draw.text((text_x, text_y), value_text, fill=value_text_color, font=font)

        logger.debug(f"Rendered gauge: value={value:.1f}, angle={angle:.1f}°")
        return img

    def _draw_ring(
        self,
        draw: ImageDraw.ImageDraw,
        center_x: int,
        center_y: int,
        radius: int,
        color: Tuple[int, int, int],
        width: int = 1,
    ):
        """Draw circle ring (outline).

        Args:
            draw: PIL ImageDraw object
            center_x: Center X
            center_y: Center Y
            radius: Circle radius
            color: RGB color
            width: Line width
        """
        draw.ellipse(
            [
                (center_x - radius, center_y - radius),
                (center_x + radius, center_y + radius),
            ],
            outline=color,
            width=width,
        )

    def _draw_gauge_arc(
        self,
        draw: ImageDraw.ImageDraw,
        center_x: int,
        center_y: int,
        radius: int,
        angle_end: float,
        color: Tuple[int, int, int],
        width: int = 2,
        angle_start: float = 0.0,
    ):
        """Draw gauge arc from start angle to end angle.

        Args:
            draw: PIL ImageDraw object
            center_x: Center X
            center_y: Center Y
            radius: Arc radius
            angle_end: End angle in degrees (0=right, 90=down, 180=left, 270=up)
            color: RGB color
            width: Line width
            angle_start: Start angle in degrees
        """
        # Draw arc using chord method (approximate with many small lines)
        import math

        angle_start_rad = math.radians(angle_start)
        angle_end_rad = math.radians(angle_end)

        steps = max(int(abs(angle_end - angle_start) * 2), 4)  # More steps for smoother arc
        for i in range(steps):
            t = i / steps
            angle = angle_start_rad + (angle_end_rad - angle_start_rad) * t
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)

            if i == 0:
                x1, y1 = x, y
            else:
                draw.line([(x1, y1), (x, y)], fill=color, width=width)
                x1, y1 = x, y

    @staticmethod
    def _clamp(value: float, min_value: float, max_value: float) -> float:
        """Clamp a value to the supplied range."""
        return max(min_value, min(max_value, value))

    @staticmethod
    def _normalize_arc_angles(angle_start: float, angle_end: float) -> tuple[float, float]:
        """Normalize an arc span so ``angle_end`` is always ahead of ``angle_start``."""
        normalized_end = angle_end
        while normalized_end <= angle_start:
            normalized_end += 360.0
        return angle_start, normalized_end

    @staticmethod
    def _interpolate_color(
        color_a: Tuple[int, int, int],
        color_b: Tuple[int, int, int],
        ratio: float,
    ) -> Tuple[int, int, int]:
        """Linearly interpolate between two RGB colors."""
        clamped = max(0.0, min(1.0, ratio))
        return tuple(
            int(round(channel_a + ((channel_b - channel_a) * clamped)))
            for channel_a, channel_b in zip(color_a, color_b)
        )

    @classmethod
    def _resolve_thresholds(
        cls,
        thresholds: Optional[Sequence[Any]],
        min_value: float,
        max_value: float,
    ) -> list[tuple[float, Tuple[int, int, int]]]:
        """Normalize threshold definitions into sorted ``(value, color)`` pairs."""
        if not thresholds:
            return [
                (min_value, (64, 128, 255)),
                (((min_value + max_value) / 2.0), (0, 220, 120)),
                (max_value, (255, 96, 64)),
            ]

        normalized: list[tuple[float, Tuple[int, int, int]]] = []
        for threshold in thresholds:
            if isinstance(threshold, dict):
                raw_value = threshold.get("value")
                raw_color = threshold.get("color")
            elif isinstance(threshold, (tuple, list)) and len(threshold) >= 2:
                raw_value, raw_color = threshold[0], threshold[1]
            else:
                continue

            try:
                color = tuple(int(channel) for channel in raw_color[:3])
                normalized.append((float(raw_value), color))
            except (TypeError, ValueError):
                continue

        if not normalized:
            return cls._resolve_thresholds(None, min_value, max_value)

        normalized.sort(key=lambda item: item[0])
        return normalized

    @classmethod
    def color_from_thresholds(
        cls,
        value: float,
        thresholds: Optional[Sequence[Any]],
        *,
        min_value: float,
        max_value: float,
    ) -> Tuple[int, int, int]:
        """Resolve a color from a threshold-gradient definition."""
        stops = cls._resolve_thresholds(thresholds, min_value, max_value)
        clamped_value = cls._clamp(value, min_value, max_value)

        if clamped_value <= stops[0][0]:
            return stops[0][1]
        if clamped_value >= stops[-1][0]:
            return stops[-1][1]

        for (left_value, left_color), (right_value, right_color) in zip(stops, stops[1:]):
            if left_value <= clamped_value <= right_value:
                span = right_value - left_value
                ratio = 0.0 if span == 0 else (clamped_value - left_value) / span
                return cls._interpolate_color(left_color, right_color, ratio)

        return stops[-1][1]

    @staticmethod
    def _resolve_bands(bands: Optional[Sequence[Any]]) -> list[dict[str, Any]]:
        """Normalize categorical band definitions into dictionaries."""
        normalized: list[dict[str, Any]] = []
        if not bands:
            return normalized

        for band in bands:
            if isinstance(band, dict):
                raw_low = band.get("low")
                raw_high = band.get("high")
                raw_color = band.get("color")
                category = band.get("category")
            elif isinstance(band, (tuple, list)) and len(band) >= 3:
                raw_low, raw_high, raw_color = band[:3]
                category = band[3] if len(band) >= 4 else None
            else:
                continue

            try:
                normalized.append(
                    {
                        "low": float(raw_low),
                        "high": float(raw_high) if raw_high is not None else None,
                        "color": tuple(int(channel) for channel in raw_color[:3]),
                        "category": str(category) if category is not None else None,
                    }
                )
            except (TypeError, ValueError):
                continue

        normalized.sort(key=lambda item: item["low"])
        return normalized

    @classmethod
    def color_from_bands(
        cls,
        value: float,
        bands: Optional[Sequence[Any]],
    ) -> Optional[Tuple[int, int, int]]:
        """Resolve the active categorical band color for a value."""
        resolved_bands = cls._resolve_bands(bands)
        if not resolved_bands:
            return None

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return resolved_bands[0]["color"]

        if numeric_value <= resolved_bands[0]["low"]:
            return resolved_bands[0]["color"]

        for band in resolved_bands:
            high = band["high"]
            if high is None:
                if numeric_value >= band["low"]:
                    return band["color"]
            elif band["low"] <= numeric_value <= high:
                return band["color"]

        return resolved_bands[-1]["color"]

    @classmethod
    def _band_display_high(
        cls,
        resolved_bands: Sequence[dict[str, Any]],
        index: int,
    ) -> float:
        """Return a finite upper bound for display/marker interpolation."""
        band = resolved_bands[index]
        if band["high"] is not None:
            return float(band["high"])

        fallback_span = None
        for previous_index in range(index - 1, -1, -1):
            previous = resolved_bands[previous_index]
            if previous["high"] is not None:
                fallback_span = float(previous["high"]) - float(previous["low"])
                break

        if fallback_span is None or fallback_span <= 0:
            fallback_span = max(1.0, float(band["low"]) or 1.0)

        return float(band["low"]) + fallback_span

    @classmethod
    def _marker_angle_for_bands(
        cls,
        value: float,
        resolved_bands: Sequence[dict[str, Any]],
        *,
        start_angle: float,
        end_angle: float,
    ) -> tuple[float, Tuple[int, int, int]]:
        """Resolve the marker angle and active band color."""
        if not resolved_bands:
            return start_angle, (255, 255, 255)

        start_angle, end_angle = cls._normalize_arc_angles(start_angle, end_angle)
        segment_sweep = (end_angle - start_angle) / len(resolved_bands)

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            numeric_value = float(resolved_bands[0]["low"])

        if numeric_value <= resolved_bands[0]["low"]:
            return start_angle, resolved_bands[0]["color"]

        for index, band in enumerate(resolved_bands):
            display_low = float(band["low"])
            display_high = cls._band_display_high(resolved_bands, index)
            if numeric_value <= display_high or index == len(resolved_bands) - 1:
                span = max(1e-6, display_high - display_low)
                fraction = max(0.0, min(1.0, (numeric_value - display_low) / span))
                band_start = start_angle + (segment_sweep * index)
                return band_start + (segment_sweep * fraction), band["color"]

        return end_angle, resolved_bands[-1]["color"]

    @staticmethod
    def _point_on_circle(
        center_x: int,
        center_y: int,
        radius: int,
        angle: float,
    ) -> tuple[float, float]:
        """Return the centerline point on a circle for a given angle."""
        angle_rad = math.radians(angle)
        return (
            center_x + (radius * math.cos(angle_rad)),
            center_y + (radius * math.sin(angle_rad)),
        )

    def _draw_arc_segment(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        center_x: int,
        center_y: int,
        radius: int,
        angle_start: float,
        angle_end: float,
        color: Tuple[int, int, int],
        width: int,
        rounded_caps: bool = False,
        round_start_cap: Optional[bool] = None,
        round_end_cap: Optional[bool] = None,
    ) -> None:
        """Draw an arc segment with optional rounded caps."""
        angle_start, angle_end = self._normalize_arc_angles(angle_start, angle_end)
        sweep = angle_end - angle_start

        if sweep <= 0:
            return

        steps = max(int(abs(sweep) * max(4.0, radius / 32.0)), 24)
        points = [
            self._point_on_circle(
                center_x,
                center_y,
                radius,
                angle_start + (sweep * (index / steps)),
            )
            for index in range(steps + 1)
        ]
        draw.line(points, fill=color, width=width)

        if round_start_cap is None:
            round_start_cap = rounded_caps
        if round_end_cap is None:
            round_end_cap = rounded_caps

        if round_start_cap or round_end_cap:
            cap_radius = max(1, width // 2)
            cap_points = []
            if round_start_cap:
                cap_points.append(points[0])
            if round_end_cap:
                cap_points.append(points[-1])
            for cap_x, cap_y in cap_points:
                draw.ellipse(
                    [
                        (cap_x - cap_radius, cap_y - cap_radius),
                        (cap_x + cap_radius, cap_y + cap_radius),
                    ],
                    fill=color,
                )

    def _render_supersampled(
        self,
        *,
        background_color: Tuple[int, int, int],
        draw_callback,
        scale: int = 4,
    ) -> Image.Image:
        """Render to a higher-resolution canvas, then downsample for smoother edges."""
        render_scale = max(1, int(scale))
        if render_scale == 1:
            img = Image.new('RGB', (self.width, self.height), background_color)
            draw = ImageDraw.Draw(img)
            draw_callback(draw, 1)
            return img

        hi_img = Image.new(
            'RGB',
            (self.width * render_scale, self.height * render_scale),
            background_color,
        )
        hi_draw = ImageDraw.Draw(hi_img)
        draw_callback(hi_draw, render_scale)
        return hi_img.resize((self.width, self.height), RESAMPLE_LANCZOS)

    def _draw_ring_pointer_marker(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        center_x: int,
        center_y: int,
        inner_radius: float,
        outer_radius: float,
        angle: float,
        fill_color: Tuple[int, int, int],
        line_color: Tuple[int, int, int],
        scale: int = 1,
    ) -> None:
        """Draw a subtle pointer marker: inner triangle plus outward hairline."""
        ring_width = max(1.0, outer_radius - inner_radius)
        triangle_length = max(6.0 * scale, ring_width * 0.8)
        triangle_half_width = max(3.0 * scale, triangle_length * 0.42)
        line_width = max(1, scale)

        angle_rad = math.radians(angle)
        perp_rad = angle_rad + (math.pi / 2.0)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        cos_p = math.cos(perp_rad)
        sin_p = math.sin(perp_rad)

        tip_x = center_x + (inner_radius * cos_a)
        tip_y = center_y + (inner_radius * sin_a)
        base_center_x = center_x + ((inner_radius - triangle_length) * cos_a)
        base_center_y = center_y + ((inner_radius - triangle_length) * sin_a)
        base_left = (
            base_center_x + (triangle_half_width * cos_p),
            base_center_y + (triangle_half_width * sin_p),
        )
        base_right = (
            base_center_x - (triangle_half_width * cos_p),
            base_center_y - (triangle_half_width * sin_p),
        )
        outer_x = center_x + (outer_radius * cos_a)
        outer_y = center_y + (outer_radius * sin_a)

        draw.polygon(
            [
                (tip_x, tip_y),
                base_left,
                base_right,
            ],
            fill=fill_color,
        )
        draw.line(
            [
                (tip_x, tip_y),
                (outer_x, outer_y),
            ],
            fill=line_color,
            width=line_width,
        )

    def _draw_needle(
        self,
        draw: ImageDraw.ImageDraw,
        center_x: int,
        center_y: int,
        radius: int,
        angle: float,
        color: Tuple[int, int, int],
        width: int = 2,
    ):
        """Draw needle pointing to angle.

        Args:
            draw: PIL ImageDraw object
            center_x: Center X
            center_y: Center Y
            radius: Needle length
            angle: Angle in degrees (0=right, 90=down, 180=left, 270=up)
            color: RGB color
            width: Line width
        """
        import math

        angle_rad = math.radians(angle)
        x_end = center_x + radius * math.cos(angle_rad)
        y_end = center_y + radius * math.sin(angle_rad)

        draw.line(
            [(center_x, center_y), (x_end, y_end)],
            fill=color,
            width=width,
        )

    def render_multi_ring_gauge(
        self,
        values: list,
        min_value: float = 0.0,
        max_value: float = 100.0,
        colors: Optional[list] = None,
        background_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> Image.Image:
        """Render gauge with multiple concentric rings.

        Each ring shows a different metric/value.

        Args:
            values: List of values (inner to outer)
            min_value: Minimum value
            max_value: Maximum value
            colors: List of RGB colors for each ring (or None for defaults)
            background_color: Background RGB color

        Returns:
            PIL Image with multi-ring gauge
        """
        if colors is None:
            # Default colors: red, yellow, green, blue
            colors = [
                (255, 0, 0),    # Red
                (255, 255, 0),  # Yellow
                (0, 255, 0),    # Green
                (0, 0, 255),    # Blue
            ]

        # Ensure we have enough colors
        while len(colors) < len(values):
            colors.append((100, 100, 100))

        img = Image.new('RGB', (self.width, self.height), background_color)
        draw = ImageDraw.Draw(img)

        # Draw each ring (outer to inner)
        for i, value in enumerate(reversed(values)):
            ring_index = len(values) - i - 1
            ring_radius = self.outer_radius - (ring_index * 20)

            if ring_radius > 20:
                # Draw background ring
                self._draw_ring(
                    draw,
                    center_x=self.center_x,
                    center_y=self.center_y,
                    radius=ring_radius,
                    color=(50, 50, 50),
                    width=1,
                )

                # Calculate angle for value
                value_range = max_value - min_value
                percentage = (value - min_value) / value_range if value_range > 0 else 0
                angle = percentage * 360.0

                # Draw gauge arc for this ring
                self._draw_gauge_arc(
                    draw,
                    center_x=self.center_x,
                    center_y=self.center_y,
                    radius=ring_radius,
                    angle_end=angle,
                    color=colors[ring_index],
                    width=6,
                )

        # Draw center circle
        draw.ellipse(
            [
                (self.center_x - 8, self.center_y - 8),
                (self.center_x + 8, self.center_y + 8),
            ],
            fill=(150, 150, 150),
        )

        logger.debug(f"Rendered multi-ring gauge with {len(values)} rings")
        return img

    def render_gradient_ring(
        self,
        value: float,
        *,
        min_value: float = 0.0,
        max_value: float = 100.0,
        thresholds: Optional[Sequence[Any]] = None,
        start_angle: float = 135.0,
        end_angle: float = 405.0,
        thickness: int = 20,
        background_color: Tuple[int, int, int] = (0, 0, 0),
        track_color: Tuple[int, int, int] = (45, 45, 45),
        rounded_caps: bool = True,
        show_marker: bool = True,
        marker_fill_color: Tuple[int, int, int] = (255, 255, 255),
        marker_outline_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Render a configurable progress ring using threshold-based gradient colors."""
        start_angle, end_angle = self._normalize_arc_angles(start_angle, end_angle)
        sweep = end_angle - start_angle
        clamped_value = self._clamp(value, min_value, max_value)
        ratio = 0.0 if max_value == min_value else (clamped_value - min_value) / (max_value - min_value)
        progress_end = start_angle + (sweep * ratio)

        def draw_gradient_ring(draw: ImageDraw.ImageDraw, scale: int) -> None:
            center_x = self.center_x * scale
            center_y = self.center_y * scale
            scaled_thickness = max(1, thickness * scale)
            ring_radius = (self.outer_radius * scale) - max(2 * scale, scaled_thickness // 2)
            inner_radius = ring_radius - (scaled_thickness / 2.0)
            outer_radius = ring_radius + (scaled_thickness / 2.0)

            self._draw_arc_segment(
                draw,
                center_x=center_x,
                center_y=center_y,
                radius=ring_radius,
                angle_start=start_angle,
                angle_end=end_angle,
                color=track_color,
                width=scaled_thickness,
                rounded_caps=rounded_caps,
            )

            if ratio <= 0:
                if show_marker:
                    marker_color = marker_outline_color or marker_fill_color
                    self._draw_ring_pointer_marker(
                        draw,
                        center_x=center_x,
                        center_y=center_y,
                        inner_radius=inner_radius,
                        outer_radius=outer_radius,
                        angle=start_angle,
                        fill_color=marker_fill_color,
                        line_color=marker_color,
                        scale=scale,
                    )
                return

            steps = max(int(abs(progress_end - start_angle) * 10), 120)
            for index in range(steps):
                segment_start = start_angle + ((progress_end - start_angle) * (index / steps))
                segment_end = start_angle + ((progress_end - start_angle) * ((index + 1) / steps))
                midpoint_ratio = (index + 0.5) / steps
                midpoint_value = min_value + ((clamped_value - min_value) * midpoint_ratio)
                segment_color = self.color_from_thresholds(
                    midpoint_value,
                    thresholds,
                    min_value=min_value,
                    max_value=max_value,
                )
                self._draw_arc_segment(
                    draw,
                    center_x=center_x,
                    center_y=center_y,
                    radius=ring_radius,
                    angle_start=segment_start,
                    angle_end=segment_end,
                    color=segment_color,
                    width=scaled_thickness,
                    rounded_caps=False,
                )

            if rounded_caps:
                cap_radius = max(1, scaled_thickness // 2)
                start_color = self.color_from_thresholds(
                    min_value,
                    thresholds,
                    min_value=min_value,
                    max_value=max_value,
                )
                end_color = self.color_from_thresholds(
                    clamped_value,
                    thresholds,
                    min_value=min_value,
                    max_value=max_value,
                )
                for angle, color in ((start_angle, start_color), (progress_end, end_color)):
                    cap_x, cap_y = self._point_on_circle(center_x, center_y, ring_radius, angle)
                    draw.ellipse(
                        [
                            (cap_x - cap_radius, cap_y - cap_radius),
                            (cap_x + cap_radius, cap_y + cap_radius),
                        ],
                        fill=color,
                    )

            if show_marker:
                marker_color = marker_outline_color or marker_fill_color
                self._draw_ring_pointer_marker(
                    draw,
                    center_x=center_x,
                    center_y=center_y,
                    inner_radius=inner_radius,
                    outer_radius=outer_radius,
                    angle=progress_end,
                    fill_color=marker_fill_color,
                    line_color=marker_color,
                    scale=scale,
                )

        return self._render_supersampled(
            background_color=background_color,
            draw_callback=draw_gradient_ring,
            scale=4,
        )

    def render_banded_ring(
        self,
        value: float,
        *,
        bands: Sequence[Any],
        start_angle: float = 135.0,
        end_angle: float = 405.0,
        thickness: int = 20,
        background_color: Tuple[int, int, int] = (0, 0, 0),
        track_color: Tuple[int, int, int] = (45, 45, 45),
        rounded_caps: bool = True,
        show_marker: bool = True,
        marker_fill_color: Tuple[int, int, int] = (255, 255, 255),
        marker_outline_color: Optional[Tuple[int, int, int]] = None,
        segment_gap_degrees: float = 0.0,
    ) -> Image.Image:
        """Render a categorical threshold ring with a visible current-value marker."""
        resolved_bands = self._resolve_bands(bands)
        if not resolved_bands:
            return Image.new('RGB', (self.width, self.height), background_color)

        start_angle, end_angle = self._normalize_arc_angles(start_angle, end_angle)
        total_sweep = end_angle - start_angle
        segment_sweep = total_sweep / len(resolved_bands)

        def draw_banded_ring(draw: ImageDraw.ImageDraw, scale: int) -> None:
            center_x = self.center_x * scale
            center_y = self.center_y * scale
            scaled_thickness = max(1, thickness * scale)
            ring_radius = (self.outer_radius * scale) - max(2 * scale, scaled_thickness // 2)
            inner_radius = ring_radius - (scaled_thickness / 2.0)
            outer_radius = ring_radius + (scaled_thickness / 2.0)

            self._draw_arc_segment(
                draw,
                center_x=center_x,
                center_y=center_y,
                radius=ring_radius,
                angle_start=start_angle,
                angle_end=end_angle,
                color=track_color,
                width=scaled_thickness,
                rounded_caps=rounded_caps,
            )

            for index, band in enumerate(resolved_bands):
                segment_start = start_angle + (segment_sweep * index)
                segment_end = segment_start + segment_sweep
                if len(resolved_bands) > 1:
                    gap = segment_gap_degrees / 2.0
                    if index > 0:
                        segment_start += gap
                    if index < len(resolved_bands) - 1:
                        segment_end -= gap
                if segment_end <= segment_start:
                    continue

                self._draw_arc_segment(
                    draw,
                    center_x=center_x,
                    center_y=center_y,
                    radius=ring_radius,
                    angle_start=segment_start,
                    angle_end=segment_end,
                    color=band["color"],
                    width=scaled_thickness,
                    round_start_cap=rounded_caps and index == 0,
                    round_end_cap=rounded_caps and index == len(resolved_bands) - 1,
                )

            if show_marker:
                marker_angle, active_color = self._marker_angle_for_bands(
                    value,
                    resolved_bands,
                    start_angle=start_angle,
                    end_angle=end_angle,
                )
                marker_color = marker_outline_color or marker_fill_color or active_color
                self._draw_ring_pointer_marker(
                    draw,
                    center_x=center_x,
                    center_y=center_y,
                    inner_radius=inner_radius,
                    outer_radius=outer_radius,
                    angle=marker_angle,
                    fill_color=marker_fill_color,
                    line_color=marker_color,
                    scale=scale,
                )

        return self._render_supersampled(
            background_color=background_color,
            draw_callback=draw_banded_ring,
            scale=4,
        )


class ProgressBar:
    """Renders linear and circular progress indicators."""

    def __init__(
        self,
        width: int = 240,
        height: int = 240,
        font_path: Optional[str] = None,
        label_font_size: int = 24,
    ):
        """Initialize progress bar renderer."""
        self.width = width
        self.height = height
        self.font_path = font_path
        self.label_font_size = label_font_size
        self._font_cache = {}

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get or load a progress label font."""
        if size not in self._font_cache:
            font, _, _ = load_font(self.font_path, size)
            self._font_cache[size] = font
        return self._font_cache[size]

    def render_linear_progress(
        self,
        progress: float,
        max_progress: float = 100.0,
        bar_height: int = 20,
        bar_color: Tuple[int, int, int] = (0, 255, 0),
        background_color: Tuple[int, int, int] = (0, 0, 0),
        border_color: Tuple[int, int, int] = (100, 100, 100),
        show_percentage: bool = True,
    ) -> Image.Image:
        """Render horizontal progress bar.

        Args:
            progress: Current progress
            max_progress: Maximum progress value
            bar_height: Bar height in pixels
            bar_color: Bar RGB color
            background_color: Background RGB color
            border_color: Border RGB color
            show_percentage: Show percentage text

        Returns:
            PIL Image with progress bar
        """
        img = Image.new('RGB', (self.width, self.height), background_color)
        draw = ImageDraw.Draw(img)

        # Bar position
        x_margin = 20
        bar_width = self.width - (x_margin * 2)
        y = (self.height - bar_height) // 2

        # Background bar (full width)
        draw.rectangle(
            [(x_margin, y), (x_margin + bar_width, y + bar_height)],
            outline=border_color,
            width=2,
        )

        # Progress bar (filled portion)
        percentage = (progress / max_progress) if max_progress > 0 else 0
        filled_width = int(bar_width * percentage)

        if filled_width > 0:
            draw.rectangle(
                [(x_margin, y), (x_margin + filled_width, y + bar_height)],
                fill=bar_color,
            )

        # Percentage text
        if show_percentage:
            pct_text = f"{(percentage * 100):.0f}%"
            font = self._get_font(self.label_font_size)
            bbox = draw.textbbox((0, 0), pct_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.width - text_width) // 2
            text_y = y + bar_height + 10
            draw.text((text_x, text_y), pct_text, fill=(255, 255, 255), font=font)

        return img

    def render_circular_progress(
        self,
        progress: float,
        max_progress: float = 100.0,
        radius: int = 100,
        ring_width: int = 10,
        progress_color: Tuple[int, int, int] = (0, 255, 0),
        background_color: Tuple[int, int, int] = (0, 0, 0),
        ring_color: Tuple[int, int, int] = (50, 50, 50),
    ) -> Image.Image:
        """Render circular progress indicator.

        Args:
            progress: Current progress
            max_progress: Maximum progress value
            radius: Circle radius
            ring_width: Ring width in pixels
            progress_color: Progress indicator RGB color
            background_color: Background RGB color
            ring_color: Ring RGB color

        Returns:
            PIL Image with circular progress
        """
        img = Image.new('RGB', (self.width, self.height), background_color)
        draw = ImageDraw.Draw(img)

        center_x = self.width // 2
        center_y = self.height // 2

        # Background ring
        draw.ellipse(
            [
                (center_x - radius, center_y - radius),
                (center_x + radius, center_y + radius),
            ],
            outline=ring_color,
            width=ring_width,
        )

        # Progress arc
        percentage = (progress / max_progress) if max_progress > 0 else 0
        angle_end = percentage * 360.0

        import math

        steps = max(int(angle_end * 2), 4)
        for i in range(steps):
            t = i / steps
            angle = t * angle_end
            angle_rad = math.radians(angle)

            x = center_x + radius * math.cos(angle_rad)
            y = center_y + radius * math.sin(angle_rad)

            if i == 0:
                x1, y1 = x, y
            else:
                draw.line([(x1, y1), (x, y)], fill=progress_color, width=ring_width)
                x1, y1 = x, y

        return img
