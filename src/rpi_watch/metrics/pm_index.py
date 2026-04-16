"""Particulate-matter health index helpers based on ATSDR Appendix B guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class PMIndexBand:
    """Single PM guidance band."""

    category: str
    severity: int
    low: float
    high: Optional[float]
    color: tuple[int, int, int]

    def contains(self, value: float) -> bool:
        """Return whether the value falls in this band."""
        if self.high is None:
            return value >= self.low
        return self.low <= value <= self.high


# High-contrast colors tuned for the watch display on a black background.
GOOD = (34, 197, 94)
MODERATE = (250, 204, 21)
USG = (251, 146, 60)
UNHEALTHY = (239, 68, 68)
VERY_UNHEALTHY = (168, 85, 247)
HAZARDOUS = (136, 19, 55)

PM25_BANDS: tuple[PMIndexBand, ...] = (
    PMIndexBand("Good", 0, 0.0, 9.0, GOOD),
    PMIndexBand("Moderate", 1, 9.1, 35.4, MODERATE),
    PMIndexBand("Unhealthy for Sensitive Groups", 2, 35.5, 55.4, USG),
    PMIndexBand("Unhealthy", 3, 55.5, 125.4, UNHEALTHY),
    PMIndexBand("Very Unhealthy", 4, 125.5, 225.4, VERY_UNHEALTHY),
    PMIndexBand("Hazardous", 5, 225.5, None, HAZARDOUS),
)

PM10_BANDS: tuple[PMIndexBand, ...] = (
    PMIndexBand("Good", 0, 0.0, 54.0, GOOD),
    PMIndexBand("Moderate", 1, 55.0, 154.0, MODERATE),
    PMIndexBand("Unhealthy for Sensitive Groups", 2, 155.0, 254.0, USG),
    PMIndexBand("Unhealthy", 3, 255.0, 354.0, UNHEALTHY),
    PMIndexBand("Very Unhealthy", 4, 355.0, 424.0, VERY_UNHEALTHY),
    PMIndexBand("Hazardous", 5, 425.0, 604.0, HAZARDOUS),
)

PM_GUIDANCE_BANDS = {
    "pm_2_5": PM25_BANDS,
    "pm_10_0": PM10_BANDS,
}


def _coerce_float(value: Any) -> Optional[float]:
    """Convert a metric-like value to float."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def get_guidance_bands(field_name: Optional[str]) -> tuple[PMIndexBand, ...]:
    """Return ATSDR guidance bands for a supported PM field."""
    if not field_name:
        return ()
    return PM_GUIDANCE_BANDS.get(str(field_name), ())


def get_guidance_display_range(field_name: Optional[str]) -> Optional[tuple[float, float]]:
    """Return a finite display range for ring rendering."""
    bands = get_guidance_bands(field_name)
    if not bands:
        return None

    lower = bands[0].low
    finite_highs = [band.high for band in bands if band.high is not None]
    if not finite_highs:
        return (lower, lower + 1.0)

    upper = finite_highs[-1]
    if bands[-1].high is None and len(bands) >= 2:
        previous = bands[-2]
        previous_span = (
            (previous.high - previous.low)
            if previous.high is not None
            else max(1.0, upper - lower)
        )
        upper = bands[-1].low + max(1.0, previous_span)

    return (lower, upper)


def classify_pm_value(field_name: Optional[str], value: Any) -> Optional[PMIndexBand]:
    """Classify a supported PM value into an ATSDR guidance band."""
    numeric_value = _coerce_float(value)
    if numeric_value is None:
        return None

    bands = get_guidance_bands(field_name)
    if not bands:
        return None

    if numeric_value <= bands[0].low:
        return bands[0]

    for band in bands:
        if band.contains(numeric_value):
            return band

    return bands[-1]


def classify_display_band(
    field_name: Optional[str],
    payload: Optional[Mapping[str, Any]],
) -> Optional[PMIndexBand]:
    """Resolve the PM guidance band used to color the displayed metric.

    PM2.5 and PM10 use their own thresholds directly.
    PM1.0 and PM4.0 inherit the worse of the PM2.5/PM10 supported bands when available.
    Non-PM metrics return ``None``.
    """
    if not field_name or not payload:
        return None

    if field_name in PM_GUIDANCE_BANDS:
        return classify_pm_value(field_name, payload.get(field_name))

    if field_name not in {"pm_1_0", "pm_4_0"}:
        return None

    candidate_bands = [
        classify_pm_value("pm_2_5", payload.get("pm_2_5")),
        classify_pm_value("pm_10_0", payload.get("pm_10_0")),
    ]
    candidate_bands = [band for band in candidate_bands if band is not None]
    if not candidate_bands:
        return None

    return max(candidate_bands, key=lambda band: band.severity)


def serialize_guidance_bands(field_name: Optional[str]) -> list[dict[str, Any]]:
    """Return guidance bands as dictionaries for rendering config."""
    return [
        {
            "category": band.category,
            "severity": band.severity,
            "low": band.low,
            "high": band.high,
            "color": band.color,
        }
        for band in get_guidance_bands(field_name)
    ]
