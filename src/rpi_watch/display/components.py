"""UI Components library for GC9A01 display.

Provides reusable components for rendering:
- Text with multiple sizes (XL, Large, Normal, Small)
- Circular gauge with concentric rings
- Progress indicators
"""

import logging
from typing import Tuple, Optional
from enum import Enum

from PIL import Image, ImageDraw, ImageFont

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

        # Load font with fallback
        self.font = self._load_font(font_path, default_font_size)
        self.fonts = {}  # Cache for different sizes

        logger.info(f"TextRenderer initialized: {width}x{height}")

    def _load_font(self, font_path: Optional[str], font_size: int) -> ImageFont.FreeTypeFont:
        """Load TrueType font with fallback."""
        if font_path is None:
            # Try common fonts
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:\\Windows\\Fonts\\arial.ttf",
            ]
            for candidate in candidates:
                try:
                    return ImageFont.truetype(candidate, font_size)
                except:
                    continue

        if font_path:
            try:
                return ImageFont.truetype(font_path, font_size)
            except:
                logger.warning(f"Could not load font {font_path}, using default")

        return ImageFont.load_default()

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get or load font at specific size."""
        if size not in self.fonts:
            self.fonts[size] = self._load_font(self.font_path, size)
        return self.fonts[size]

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


class CircularGauge:
    """Renders circular gauge with concentric rings and needle."""

    def __init__(
        self,
        width: int = 240,
        height: int = 240,
        center_x: Optional[int] = None,
        center_y: Optional[int] = None,
        outer_radius: int = 110,
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

        logger.info(f"CircularGauge initialized: {width}x{height}, radius={outer_radius}")

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
            font = ImageFont.load_default()
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


class ProgressBar:
    """Renders linear and circular progress indicators."""

    def __init__(self, width: int = 240, height: int = 240):
        """Initialize progress bar renderer."""
        self.width = width
        self.height = height

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
            font = ImageFont.load_default()
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
