"""Shared font resolution helpers for display rendering."""

import logging
import subprocess
from functools import lru_cache
from typing import Optional

from PIL import ImageFont

logger = logging.getLogger(__name__)


FONTCONFIG_QUERIES = (
    "DejaVu Sans:style=Bold",
    "DejaVu Sans:style=Book",
    "Noto Sans:style=Bold",
    "Noto Sans:style=Regular",
    "Liberation Sans:style=Bold",
    "Liberation Sans:style=Regular",
    "FreeSans:style=Bold",
)

FONT_CANDIDATES = (
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    "NotoSans-Bold.ttf",
    "NotoSans-Regular.ttf",
    "LiberationSans-Bold.ttf",
    "LiberationSans-Regular.ttf",
    "FreeSansBold.ttf",
    "Arial Bold.ttf",
    "Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
)


def _dedupe(values: list[str]) -> list[str]:
    """Return items in order without duplicates."""
    seen = set()
    deduped = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


@lru_cache(maxsize=32)
def _fc_match(query: str) -> Optional[str]:
    """Resolve a fontconfig query to a concrete font file path."""
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}\n", query],
            capture_output=True,
            text=True,
            check=False,
            timeout=1.0,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    resolved = result.stdout.strip()
    return resolved or None


@lru_cache(maxsize=32)
def resolve_font_source(font_path: Optional[str] = None) -> Optional[str]:
    """Resolve the best available scalable font source for this host."""
    candidates: list[str] = []
    if font_path:
        candidates.append(font_path)
        matched = _fc_match(font_path)
        if matched:
            candidates.append(matched)

    for query in FONTCONFIG_QUERIES:
        matched = _fc_match(query)
        if matched:
            candidates.append(matched)

    candidates.extend(FONT_CANDIDATES)

    for candidate in _dedupe(candidates):
        try:
            ImageFont.truetype(candidate, 24)
            return candidate
        except (OSError, IOError):
            continue

    return None


def load_font(
    font_path: Optional[str],
    font_size: int,
) -> tuple[ImageFont.ImageFont, Optional[str], bool]:
    """Load a scalable font when possible, otherwise return Pillow default."""
    resolved_source = resolve_font_source(font_path)
    if resolved_source:
        try:
            return (ImageFont.truetype(resolved_source, font_size), resolved_source, True)
        except (OSError, IOError) as exc:
            logger.warning(f"Resolved font failed to load ({resolved_source}): {exc}")

    logger.warning(
        "No scalable font source could be loaded for requested font '%s'; using Pillow default",
        font_path,
    )
    return (ImageFont.load_default(), None, False)
