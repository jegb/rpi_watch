"""Graphics renderer for numeric metrics with circular mask support.

Converts numeric values to PIL Images with proper formatting and applies
circular masking for the round 240x240 display.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class MetricRenderer:
    """Renders numeric metrics as PIL Images with circular masking."""

    def __init__(
        self,
        width: int = 240,
        height: int = 240,
        font_path: Optional[str] = None,
        font_size: int = 80,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        background_color: Tuple[int, int, int] = (0, 0, 0),
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
        self.font_size = font_size
        self.text_color = text_color
        self.background_color = background_color

        # Initialize font
        self.font = self._load_font(font_path, font_size)

        # Pre-compute circular mask once for efficiency
        self.circular_mask = self._create_circular_mask()

        logger.info(
            f"MetricRenderer initialized: {width}x{height}, "
            f"font_size={font_size}, font_path={font_path}"
        )

    def _load_font(self, font_path: Optional[str], font_size: int) -> ImageFont.FreeTypeFont:
        """Load a TrueType font.

        Args:
            font_path: Path to font file. If None, uses a default system font.
            font_size: Font size in points

        Returns:
            Loaded ImageFont object
        """
        if font_path is None:
            # Try common default fonts
            default_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
                "C:\\Windows\\Fonts\\arial.ttf",  # Windows fallback
            ]
            for font_candidate in default_fonts:
                try:
                    return ImageFont.truetype(font_candidate, font_size)
                except (IOError, OSError):
                    continue
            # Fallback to default font
            logger.warning("No TrueType font found, using default font (may be limited)")
            return ImageFont.load_default()

        try:
            font_obj = ImageFont.truetype(font_path, font_size)
            logger.info(f"Loaded font: {font_path}")
            return font_obj
        except (IOError, OSError) as e:
            logger.warning(f"Failed to load font {font_path}: {e}. Using default.")
            return ImageFont.load_default()

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

    def render_metric(
        self,
        value: float,
        decimal_places: int = 1,
        unit_label: str = "",
    ) -> Image.Image:
        """Render a numeric metric as a PIL Image.

        Args:
            value: Numeric value to display
            decimal_places: Number of decimal places to show
            unit_label: Optional unit string (e.g., "°C", "W")

        Returns:
            PIL Image (RGB, 240x240) with the metric value centered
        """
        # Format the value
        if decimal_places >= 0:
            formatted_value = f"{value:.{decimal_places}f}"
        else:
            formatted_value = str(int(value))

        if unit_label:
            text = f"{formatted_value}{unit_label}"
        else:
            text = formatted_value

        # Create base image with background color
        image = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Measure text bounding box to center it
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Center text on image
        text_x = (self.width - text_width) // 2
        text_y = (self.height - text_height) // 2

        # Draw text
        draw.text((text_x, text_y), text, fill=self.text_color, font=self.font)

        logger.debug(f"Rendered metric: value={value}, text='{text}'")

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
        value: float,
        decimal_places: int = 1,
        unit_label: str = "",
    ) -> Image.Image:
        """Render metric and apply circular mask in one step.

        Args:
            value: Numeric value to display
            decimal_places: Number of decimal places to show
            unit_label: Optional unit string (e.g., "°C", "W")

        Returns:
            PIL Image (RGB, 240x240) with metric value and circular mask applied
        """
        image = self.render_metric(value, decimal_places, unit_label)
        masked_image = self.apply_circular_mask(image)
        return masked_image
