"""Page size in physical units, and the DPI that makes it mean something.

A page is usually specified in **pixels**. That is a complete description for a
screen and an incomplete one for print: 3000 px is 10 inches at 300 DPI and
41.7 inches at 72 DPI, and nothing in the file says which unless something
writes the resolution into it.

This module is the other half of that. It lets a caller say what they actually
mean — "A4 at 300 DPI", "8x10in at 300" — and get back the pixel dimensions
*together with* the DPI they were derived at, so the two numbers cannot
disagree. Pass :attr:`PageGeometry.dpi` to your encoder (Pillow takes
``dpi=(x, y)`` on both PNG and JPEG saves) and the file then says what it is.

Nothing here imports Pillow, or anything else. It is arithmetic with the
constants written down.

.. note::
   A PNG stores resolution in its ``pHYs`` chunk as pixels *per metre*, as an
   integer. 300 DPI is 11811.02... px/m, so it is stored as 11811 and reads
   back as 299.9994 rather than 300. That is the format, not a defect; compare
   with a tolerance rather than for equality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "DEFAULT_DPI",
    "MM_PER_INCH",
    "NAMED_PAGE_SIZES_MM",
    "PageGeometry",
    "PageUnit",
    "named_page_geometry",
    "resolve_page_geometry",
    "to_pixels",
    "validate_dpi",
]

# 300 DPI is the ordinary floor for photographic print. It is the default here
# because the page presets are print-shaped (3000x4000 = 10x13.3in at 300).
DEFAULT_DPI = 300

MM_PER_INCH = 25.4

PageUnit = Literal["px", "in", "mm"]

# Common page sizes in millimetres, for callers that would rather name one.
NAMED_PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "a3": (297.0, 420.0),
    "a5": (148.0, 210.0),
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
    "tabloid": (279.4, 431.8),
}


@dataclass(frozen=True, slots=True)
class PageGeometry:
    """A page's pixel dimensions together with the DPI they were derived at."""

    width_px: int
    height_px: int
    dpi: int

    @property
    def width_inches(self) -> float:
        return self.width_px / self.dpi

    @property
    def height_inches(self) -> float:
        return self.height_px / self.dpi

    @property
    def description(self) -> str:
        return (
            f"{self.width_px}x{self.height_px}px "
            f"({self.width_inches:.2f}x{self.height_inches:.2f}in at {self.dpi} DPI)"
        )


def to_pixels(value: float, unit: PageUnit, dpi: int) -> int:
    """Convert ``value`` in ``unit`` to whole pixels at ``dpi``."""
    if value <= 0:
        raise ValueError("Page dimensions must be greater than zero.")
    if unit == "px":
        pixels = value
    elif unit == "in":
        pixels = value * dpi
    elif unit == "mm":
        pixels = (value / MM_PER_INCH) * dpi
    else:
        raise ValueError(f"Unsupported unit '{unit}'. Use 'px', 'in' or 'mm'.")

    rounded = int(round(pixels))
    if rounded <= 0:
        raise ValueError("Page dimensions rounded to zero pixels; increase the size or DPI.")
    return rounded


def resolve_page_geometry(
    *,
    page_width: float,
    page_height: float,
    unit: PageUnit = "px",
    dpi: int = DEFAULT_DPI,
) -> PageGeometry:
    """Resolve a requested page size to pixels at ``dpi``.

    With ``unit="px"`` the dimensions pass through unchanged and ``dpi`` only
    decides what gets written into the exported file's metadata — which is the
    backward-compatible path every existing caller takes.
    """
    validate_dpi(dpi)
    return PageGeometry(
        width_px=to_pixels(page_width, unit, dpi),
        height_px=to_pixels(page_height, unit, dpi),
        dpi=dpi,
    )


def named_page_geometry(name: str, *, dpi: int = DEFAULT_DPI) -> PageGeometry:
    """Resolve a named page size (``a4``, ``letter``, ...) at ``dpi``."""
    key = name.strip().lower()
    if key not in NAMED_PAGE_SIZES_MM:
        supported = ", ".join(sorted(NAMED_PAGE_SIZES_MM))
        raise ValueError(f"Unknown page size '{name}'. Supported: {supported}.")

    width_mm, height_mm = NAMED_PAGE_SIZES_MM[key]
    return resolve_page_geometry(
        page_width=width_mm,
        page_height=height_mm,
        unit="mm",
        dpi=dpi,
    )


def validate_dpi(dpi: int) -> int:
    """Reject a DPI that would make the export meaningless."""
    if dpi <= 0:
        raise ValueError("DPI must be greater than zero.")
    if dpi > 1200:
        raise ValueError("DPI above 1200 is not supported.")
    return int(dpi)
