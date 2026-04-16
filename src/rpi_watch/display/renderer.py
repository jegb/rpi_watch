"""Graphics renderer for numeric metrics with circular mask support.

Converts numeric values to PIL Images with proper formatting and applies
circular masking for the round 240x240 display.
"""

import logging
from typing import Any, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from .components import SparklineRenderer
from .fonts import load_font

logger = logging.getLogger(__name__)


class MetricRenderer:
    """Renders numeric metrics as PIL Images with circular masking."""

    def __init__(
        self,
        width: int = 240,
        height: int = 240,
        font_path: Optional[str] = None,
        font_size: int = 80,
        title_font_size: Optional[int] = None,
        unit_font_size: Optional[int] = None,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        background_color: Tuple[int, int, int] = (0, 0, 0),
        padding: int = 18,
        title_gap: int = 10,
        unit_gap: int = 6,
        sparkline_height: int = 32,
        sparkline_gap: int = 10,
    ):
        """Initialize the renderer.

        Args:
            width: Image width in pixels
            height: Image height in pixels
            font_path: Path to TrueType font file. If None, uses default.
            font_size: Font size in points
            text_color: RGB tuple for text color
            background_color: RGB tuple for background color
        """
        self.width = width
        self.height = height
        self.font_path = font_path
        self.font_size = font_size
        self.unit_font_size = unit_font_size or max(24, int(font_size * 0.30))
        self.title_font_size = title_font_size or self.unit_font_size
        self.text_color = text_color
        self.background_color = background_color
        self.padding = padding
        self.title_gap = title_gap
        self.unit_gap = unit_gap
        self.sparkline_height = sparkline_height
        self.sparkline_gap = sparkline_gap
        self._font_cache = {}
        self.resolved_font_source = None
        self.using_scalable_font = False

        # Initialize font
        self.font = self._load_font(font_path, font_size)
        self.title_font = self._load_font(font_path, self.title_font_size)
        self.unit_font = self._load_font(font_path, self.unit_font_size)

        # Pre-compute circular mask once for efficiency
        self.circular_mask = self._create_circular_mask()

        logger.info(
            f"MetricRenderer initialized: {width}x{height}, "
            f"font_size={font_size}, title_font_size={self.title_font_size}, "
            f"unit_font_size={self.unit_font_size}, "
            f"title_gap={self.title_gap}, unit_gap={self.unit_gap}, "
            f"sparkline_height={self.sparkline_height}, sparkline_gap={self.sparkline_gap}, "
            f"font_path={font_path}, resolved_font={self.resolved_font_source}, "
            f"scalable_font={self.using_scalable_font}"
        )

    @staticmethod
    def _measure_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
    ) -> tuple[tuple[int, int, int, int], int, int]:
        """Return the bbox, width, and height for a text run."""
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox, bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _load_font(self, font_path: Optional[str], font_size: int) -> ImageFont.FreeTypeFont:
        """Load a TrueType font.

        Args:
            font_path: Path to font file. If None, uses a default system font.
            font_size: Font size in points

        Returns:
            Loaded ImageFont object
        """
        cache_key = (font_path, font_size)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font_obj, resolved_source, used_scalable_font = load_font(font_path, font_size)
        if resolved_source and self.resolved_font_source is None:
            self.resolved_font_source = resolved_source
        self.using_scalable_font = self.using_scalable_font or used_scalable_font
        self._font_cache[cache_key] = font_obj
        return font_obj

    def _fit_font(
        self,
        text: str,
        base_size: int,
        max_width: int,
        min_size: int,
        max_height: Optional[int] = None,
    ) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
        """Reduce font size until text fits the requested width."""
        scratch = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(scratch)

        for size in range(base_size, min_size - 1, -2):
            font = self._load_font(self.font_path, size)
            bbox, text_width, text_height = self._measure_text(draw, text, font)
            if text_width <= max_width and (max_height is None or text_height <= max_height):
                return font, bbox

        font = self._load_font(self.font_path, min_size)
        bbox, _, _ = self._measure_text(draw, text, font)
        return font, bbox

    def _create_circular_mask(self) -> Image.Image:
        """Create a circular mask for the round display.

        Returns:
            PIL Image in mode 'L' (grayscale) with white circle on black background
        """
        mask = Image.new('L', (self.width, self.height), 0)  # Black background
        draw = ImageDraw.Draw(mask)

        # Draw white circle (255 = fully opaque in mask)
        # Circle is inscribed in the square, so diameter = width/height
        radius = min(self.width, self.height) // 2
        center_x, center_y = self.width // 2, self.height // 2

        # Draw filled ellipse (circle) in white
        draw.ellipse(
            [
                (center_x - radius, center_y - radius),
                (center_x + radius, center_y + radius),
            ],
            fill=255,
        )

        logger.debug(f"Circular mask created: radius={radius}, center=({center_x}, {center_y})")
        return mask

    def _render_text_block(
        self,
        display_text: str,
        title_label: str = "",
        unit_label: str = "",
        sparkline_values: Optional[Sequence[Any]] = None,
        sparkline_color: Optional[Tuple[int, int, int]] = None,
        sparkline_reference_value: Optional[float] = None,
        sparkline_reference_color: Optional[Tuple[int, int, int]] = None,
        value_color: Optional[Tuple[int, int, int]] = None,
        label_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Render arbitrary display text with optional title and unit lines."""
        image = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(image)
        value_color = value_color or self.text_color
        label_color = label_color or self.text_color

        max_text_width = self.width - (self.padding * 2)
        sparkline_values = list(sparkline_values or [])
        has_sparkline = len(sparkline_values) >= 2
        available_text_height = self.height - (self.padding * 2)
        if has_sparkline:
            available_text_height -= self.sparkline_height + self.sparkline_gap

        lines: list[dict[str, Any]]
        title_line: Optional[dict[str, Any]] = None
        unit_line: Optional[dict[str, Any]] = None

        if title_label:
            title_font, title_bbox = self._fit_font(
                title_label,
                self.title_font_size,
                max_width=max_text_width,
                min_size=max(18, int(self.title_font_size * 0.75)),
                max_height=max(18, int(available_text_height * 0.18)),
            )
            title_line = {
                "text": title_label,
                "font": title_font,
                "width": title_bbox[2] - title_bbox[0],
                "height": title_bbox[3] - title_bbox[1],
                "top": title_bbox[1],
                "kind": "label",
                "gap_after": self.title_gap,
            }

        if unit_label:
            unit_font, unit_bbox = self._fit_font(
                unit_label,
                self.unit_font_size,
                max_width=max_text_width,
                min_size=max(18, int(self.unit_font_size * 0.75)),
                max_height=max(18, int(available_text_height * 0.18)),
            )
            unit_line = {
                "text": unit_label,
                "font": unit_font,
                "width": unit_bbox[2] - unit_bbox[0],
                "height": unit_bbox[3] - unit_bbox[1],
                "top": unit_bbox[1],
                "kind": "label",
                "gap_after": 0,
            }

        value_min_size = max(30, int(self.font_size * 0.50))
        chosen_value_font: ImageFont.FreeTypeFont | None = None
        chosen_value_bbox: tuple[int, int, int, int] | None = None
        lines = []

        for value_size in range(self.font_size, value_min_size - 1, -2):
            value_font = self._load_font(self.font_path, value_size)
            value_bbox, value_width, value_height = self._measure_text(draw, display_text, value_font)

            candidate_lines = []
            if title_line:
                candidate_lines.append(dict(title_line))
            candidate_lines.append(
                {
                    "text": display_text,
                    "font": value_font,
                    "width": value_width,
                    "height": value_height,
                    "top": value_bbox[1],
                    "kind": "value",
                    "gap_after": self.unit_gap if unit_line else 0,
                }
            )
            if unit_line:
                candidate_lines.append(dict(unit_line))

            total_height = sum(line["height"] + line["gap_after"] for line in candidate_lines)
            if value_width <= max_text_width and total_height <= available_text_height:
                chosen_value_font = value_font
                chosen_value_bbox = value_bbox
                lines = candidate_lines
                break

        if chosen_value_font is None or chosen_value_bbox is None:
            chosen_value_font, chosen_value_bbox = self._fit_font(
                display_text,
                value_min_size,
                max_width=max_text_width,
                min_size=max(24, int(value_min_size * 0.75)),
                max_height=max(24, available_text_height),
            )
            value_width = chosen_value_bbox[2] - chosen_value_bbox[0]
            value_height = chosen_value_bbox[3] - chosen_value_bbox[1]
            lines = []
            if title_line:
                lines.append(dict(title_line))
            lines.append(
                {
                    "text": display_text,
                    "font": chosen_value_font,
                    "width": value_width,
                    "height": value_height,
                    "top": chosen_value_bbox[1],
                    "kind": "value",
                    "gap_after": self.unit_gap if unit_line else 0,
                }
            )
            if unit_line:
                lines.append(dict(unit_line))

        total_height = sum(line["height"] + line["gap_after"] for line in lines)
        current_y = self.padding + max(0, (available_text_height - total_height) // 2)

        for line in lines:
            text_x = (self.width - line["width"]) // 2
            draw_y = current_y - line["top"]
            draw.text(
                (text_x, draw_y),
                line["text"],
                fill=value_color if line.get("kind") == "value" else label_color,
                font=line["font"],
            )
            current_y += line["height"] + line["gap_after"]

        if has_sparkline:
            sparkline_renderer = SparklineRenderer(
                width=self.width - (self.padding * 2),
                height=self.sparkline_height,
                padding=2,
            )
            fill_color = tuple(max(0, min(255, int(channel * 0.22))) for channel in (sparkline_color or self.text_color))
            sparkline_image = sparkline_renderer.render(
                sparkline_values,
                background_color=self.background_color,
                line_color=sparkline_color or self.text_color,
                fill_color=fill_color,
                stroke_width=2,
                point_radius=2,
                reference_value=sparkline_reference_value,
                reference_color=sparkline_reference_color,
                reference_width=2,
            )
            image.paste(
                sparkline_image,
                (self.padding, self.height - self.padding - self.sparkline_height),
            )

        return image

    def render_metric(
        self,
        value: float | str,
        decimal_places: int = 1,
        title_label: str = "",
        unit_label: str = "",
        sparkline_values: Optional[Sequence[Any]] = None,
        sparkline_color: Optional[Tuple[int, int, int]] = None,
        sparkline_reference_value: Optional[float] = None,
        sparkline_reference_color: Optional[Tuple[int, int, int]] = None,
        value_color: Optional[Tuple[int, int, int]] = None,
        label_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Render a metric as a PIL Image.

        Args:
            value: Numeric value or placeholder text to display
            decimal_places: Number of decimal places to show
            title_label: Optional title string (e.g., "PM2.5", "TEMP")
            unit_label: Optional unit string (e.g., "°C", "W")

        Returns:
            PIL Image (RGB, 240x240) with the metric value centered
        """
        if isinstance(value, str):
            formatted_value = value
        else:
            if decimal_places >= 0:
                formatted_value = f"{value:.{decimal_places}f}"
            else:
                formatted_value = str(int(value))

        image = self._render_text_block(
            formatted_value,
            title_label=title_label,
            unit_label=unit_label,
            sparkline_values=sparkline_values,
            sparkline_color=sparkline_color,
            sparkline_reference_value=sparkline_reference_value,
            sparkline_reference_color=sparkline_reference_color,
            value_color=value_color,
            label_color=label_color,
        )

        logger.debug(
            f"Rendered metric: value={value}, text='{formatted_value}', "
            f"title='{title_label}', unit='{unit_label}'"
        )

        return image

    def apply_circular_mask(self, image: Image.Image) -> Image.Image:
        """Apply circular mask to an image for the round display.

        Args:
            image: PIL Image (should be 240x240 RGB)

        Returns:
            PIL Image with circular mask applied (content outside circle is black)
        """
        if image.size != (self.width, self.height):
            logger.warning(f"Image size {image.size} != renderer size {(self.width, self.height)}")
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

        # Ensure image is RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Create output image
        output = Image.new('RGB', (self.width, self.height), self.background_color)

        # Apply mask using composite
        # This keeps pixels where mask is white (255), replaces with background_color where black (0)
        output = Image.composite(image, output, self.circular_mask)

        logger.debug("Circular mask applied")
        return output

    def render_and_mask(
        self,
        value: float | str,
        decimal_places: int = 1,
        title_label: str = "",
        unit_label: str = "",
        sparkline_values: Optional[Sequence[Any]] = None,
        sparkline_color: Optional[Tuple[int, int, int]] = None,
        sparkline_reference_value: Optional[float] = None,
        sparkline_reference_color: Optional[Tuple[int, int, int]] = None,
        value_color: Optional[Tuple[int, int, int]] = None,
        label_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Render metric and apply circular mask in one step.

        Args:
            value: Numeric value to display
            decimal_places: Number of decimal places to show
            title_label: Optional title string (e.g., "PM2.5", "TEMP")
            unit_label: Optional unit string (e.g., "°C", "W")

        Returns:
            PIL Image (RGB, 240x240) with metric value and circular mask applied
        """
        image = self.render_metric(
            value,
            decimal_places=decimal_places,
            title_label=title_label,
            unit_label=unit_label,
            sparkline_values=sparkline_values,
            sparkline_color=sparkline_color,
            sparkline_reference_value=sparkline_reference_value,
            sparkline_reference_color=sparkline_reference_color,
            value_color=value_color,
            label_color=label_color,
        )
        masked_image = self.apply_circular_mask(image)
        return masked_image
