"""Graphics renderer for numeric metrics with circular mask support.

Converts numeric values to PIL Images with proper formatting and applies
circular masking for the round 240x240 display.
"""

import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

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
        unit_gap: int = 6,
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
        self.unit_gap = unit_gap
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
            f"font_path={font_path}, resolved_font={self.resolved_font_source}, "
            f"scalable_font={self.using_scalable_font}"
        )

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
    ) -> ImageFont.FreeTypeFont:
        """Reduce font size until text fits the requested width."""
        scratch = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(scratch)

        for size in range(base_size, min_size - 1, -2):
            font = self._load_font(self.font_path, size)
            bbox = draw.textbbox((0, 0), text, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                return font

        return self._load_font(self.font_path, min_size)

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
    ) -> Image.Image:
        """Render arbitrary display text with optional title and unit lines."""
        image = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(image)

        max_text_width = self.width - (self.padding * 2)
        value_font = self._fit_font(
            display_text,
            self.font_size,
            max_width=max_text_width,
            min_size=max(42, int(self.font_size * 0.60)),
        )
        value_bbox = draw.textbbox((0, 0), display_text, font=value_font)
        value_width = value_bbox[2] - value_bbox[0]
        value_height = value_bbox[3] - value_bbox[1]

        lines = []

        if title_label:
            title_font = self._fit_font(
                title_label,
                self.title_font_size,
                max_width=max_text_width,
                min_size=max(18, int(self.title_font_size * 0.75)),
            )
            title_bbox = draw.textbbox((0, 0), title_label, font=title_font)
            lines.append(
                (
                    title_label,
                    title_font,
                    title_bbox[2] - title_bbox[0],
                    title_bbox[3] - title_bbox[1],
                )
            )

        lines.append((display_text, value_font, value_width, value_height))

        if unit_label:
            unit_font = self._fit_font(
                unit_label,
                self.unit_font_size,
                max_width=max_text_width,
                min_size=max(18, int(self.unit_font_size * 0.75)),
            )
            unit_bbox = draw.textbbox((0, 0), unit_label, font=unit_font)
            lines.append(
                (
                    unit_label,
                    unit_font,
                    unit_bbox[2] - unit_bbox[0],
                    unit_bbox[3] - unit_bbox[1],
                )
            )

        total_height = sum(line[3] for line in lines)
        total_height += self.unit_gap * max(0, len(lines) - 1)
        current_y = (self.height - total_height) // 2 - 8

        for text, font, text_width, text_height in lines:
            text_x = (self.width - text_width) // 2
            draw.text((text_x, current_y), text, fill=self.text_color, font=font)
            current_y += text_height + self.unit_gap

        return image

    def render_metric(
        self,
        value: float | str,
        decimal_places: int = 1,
        title_label: str = "",
        unit_label: str = "",
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
        )
        masked_image = self.apply_circular_mask(image)
        return masked_image
