"""Clean a near-white background so a subject sits flush on a white surface.

The problem is visible on any page or card built from photographed or
JPEG-compressed source images: a "white" background is rarely ``#FFFFFF``. It
is ``#FBFBFA`` from a scanner, ``#F7F8F9`` from a phone's auto white balance,
or a ring of ``#FDFDFD`` compression noise around a cutout. Every one of those
reads as a faint rectangle around the image — a grid looks gridded, a card
looks pasted on, exactly where the design wanted neither.

Two rules make this reliable rather than destructive.

**Only clean what touches the border.** A global "every pixel brighter than
``threshold`` becomes white" pass is the obvious implementation and it eats the
subject: the highlight on a white mug, the page of an open book, a bride's
dress, the sky behind a building. This module flood-fills *inward from the
edges* instead, so a pixel is only cleaned when there is a continuous
near-white path from it to the frame. Interior highlights are unreachable and
are therefore never touched.

**Decide per image whether there is a background at all.** An image whose
border is not near-white — a full-bleed photograph, a dark render — is returned
untouched rather than partially eaten. ``border_tolerance`` draws that line,
and :func:`looks_like_white_background` answers it on its own so a caller can
*report* the decision instead of silently doing nothing.

Output modes differ only in what the cleaned region becomes:

``flatten``      the region becomes the matte colour — what a white page wants.
``transparent``  the region becomes alpha 0, for a caller compositing onto a
                 non-white surface, or writing a cutout PNG.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from .source import WHITE, Matte

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL.Image import Image as PILImage

__all__ = [
    "DEFAULT_BORDER_COVERAGE",
    "DEFAULT_BORDER_TOLERANCE",
    "DEFAULT_TOLERANCE",
    "BackgroundCleanMode",
    "CleanResult",
    "clean_background",
    "keeps_alpha",
    "looks_like_white_background",
]

# A pixel is "near white" when every channel is at or above this value. 240 is
# deliberately conservative: it clears JPEG noise and scanner grey while
# leaving genuinely light-grey subject matter (a #E8E8E8 product shadow) alone.
DEFAULT_TOLERANCE = 240

# How near-white the frame itself must be, on average, before this image is
# treated as having a white background at all.
DEFAULT_BORDER_TOLERANCE = 232

# Fraction of the border that must read as near-white. One dark object running
# off the edge of an otherwise white product shot should not disqualify it.
DEFAULT_BORDER_COVERAGE = 0.55


class BackgroundCleanMode(StrEnum):
    """What the detected background region becomes."""

    OFF = "off"
    FLATTEN = "flatten"
    TRANSPARENT = "transparent"


def keeps_alpha(mode: BackgroundCleanMode | str) -> bool:
    """Whether ``mode`` needs the source image's own alpha channel preserved.

    Exists so a caller picking an open mode does not have to restate the rule::

        image = open_path(p, keep_alpha=keeps_alpha(mode))
        cleaned, result = clean_background(image, mode=mode)

    Getting it wrong is quiet rather than loud: an already-transparent PNG
    opened without ``keep_alpha`` is flattened onto white *before* it is
    cleaned, so its anti-aliased edges keep the white they were blended with
    and the cutout comes back with a pale fringe.
    """
    return BackgroundCleanMode(str(mode)) is BackgroundCleanMode.TRANSPARENT


@dataclass(frozen=True, slots=True)
class CleanResult:
    """What a clean pass did, so callers can report rather than guess."""

    cleaned: bool
    reason: str
    background_ratio: float

    @property
    def message(self) -> str:
        """A sentence fit to show a user, either way."""
        if self.cleaned:
            return f"Cleaned background ({self.background_ratio:.0%} of the image)."
        return self.reason


def _border_pixels(image: PILImage) -> list[tuple[int, int, int]]:
    """The one-pixel frame around ``image``, as RGB triples."""
    width, height = image.size
    if width == 0 or height == 0:
        return []

    pixels = image.load()
    frame: list[tuple[int, int, int]] = []
    for x in range(width):
        frame.append(pixels[x, 0])
        if height > 1:
            frame.append(pixels[x, height - 1])
    for y in range(1, max(1, height - 1)):
        frame.append(pixels[0, y])
        if width > 1:
            frame.append(pixels[width - 1, y])
    return frame


def looks_like_white_background(
    image: PILImage | Any,
    *,
    border_tolerance: int = DEFAULT_BORDER_TOLERANCE,
    border_coverage: float = DEFAULT_BORDER_COVERAGE,
) -> bool:
    """Whether enough of ``image``'s frame is near-white to call it a background.

    Asked *before* any pixel is modified. An image that fails it is returned
    untouched — a full-bleed photograph has no background to clean, and
    flood-filling from its corners would eat whatever happens to be light
    there.
    """
    frame = _border_pixels(image.convert("RGB"))
    if not frame:
        return False

    near_white = sum(1 for pixel in frame if min(pixel) >= border_tolerance)
    return (near_white / len(frame)) >= border_coverage


def _background_mask(image: PILImage, *, tolerance: int) -> tuple[PILImage, float]:
    """A mask of the edge-connected near-white region, and its area ratio.

    White in the mask means background. Built by flood-filling a scratch canvas
    inward from every border pixel that is already near-white, so interior
    highlights of the same colour are unreachable and survive.
    """
    from PIL import ImageDraw

    width, height = image.size
    greyscale = image.convert("L")

    # Everything near-white starts as a fill candidate (255); everything else
    # is a wall (0). The flood then decides which candidates are edge-connected.
    candidates = greyscale.point(lambda level: 255 if level >= tolerance else 0)

    # Pillow's floodfill spreads across equal-ish values, so seeding a third
    # value (128) marks exactly the reached region and leaves unreachable
    # candidates at 255 to be discarded below.
    working = candidates.copy()
    working_pixels = working.load()

    seeds: list[tuple[int, int]] = []
    for x in range(width):
        seeds.append((x, 0))
        if height > 1:
            seeds.append((x, height - 1))
    for y in range(height):
        seeds.append((0, y))
        if width > 1:
            seeds.append((width - 1, y))

    for seed in seeds:
        # Read through the access object rather than getpixel: floodfill
        # mutates ``working`` in place and the access object sees it, so this
        # also skips seeds an earlier flood has already swallowed.
        if working_pixels[seed] == 255:
            ImageDraw.floodfill(working, seed, 128, thresh=0)

    mask = working.point(lambda level: 255 if level == 128 else 0)

    histogram = mask.histogram()
    background_pixels = histogram[255] if len(histogram) > 255 else 0
    total = width * height
    return mask, (background_pixels / total if total else 0.0)


def clean_background(
    image: PILImage | Any,
    *,
    mode: BackgroundCleanMode | str = BackgroundCleanMode.FLATTEN,
    tolerance: int = DEFAULT_TOLERANCE,
    border_tolerance: int = DEFAULT_BORDER_TOLERANCE,
    border_coverage: float = DEFAULT_BORDER_COVERAGE,
    feather: int = 1,
    matte: Matte = WHITE,
) -> tuple[PILImage, CleanResult]:
    """Return ``image`` with its edge-connected near-white background cleaned.

    ``feather`` softens the mask by that many pixels before it is applied,
    which is what removes the grey halo left by anti-aliased cutout edges. Pass
    ``0`` for a hard edge.

    The image is never mutated; when nothing is cleaned it is returned as-is,
    which is what lets a caller pass every image through unconditionally.
    """
    from PIL import Image, ImageChops, ImageFilter

    normalized_mode = BackgroundCleanMode(str(mode))
    if normalized_mode is BackgroundCleanMode.OFF:
        return image, CleanResult(False, "Background cleaning is off.", 0.0)

    if not 0 <= tolerance <= 255:
        raise ValueError("tolerance must be between 0 and 255.")
    if feather < 0:
        raise ValueError("feather must be zero or greater.")

    rgb = image.convert("RGB")
    if not looks_like_white_background(
        rgb,
        border_tolerance=border_tolerance,
        border_coverage=border_coverage,
    ):
        return image, CleanResult(
            False,
            "No white background detected; image left unchanged.",
            0.0,
        )

    mask, background_ratio = _background_mask(rgb, tolerance=tolerance)
    if background_ratio <= 0:
        return image, CleanResult(
            False,
            "No background pixels matched the tolerance.",
            0.0,
        )

    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))

    if normalized_mode is BackgroundCleanMode.TRANSPARENT:
        cleaned = image.convert("RGBA")
        # Subtract the background mask from whatever alpha the image already
        # carries, so an already-cut-out PNG is not given its corners back.
        cleaned.putalpha(ImageChops.subtract(cleaned.getchannel("A"), mask))
    else:
        cleaned = Image.composite(Image.new("RGB", rgb.size, matte), rgb, mask)

    return cleaned, CleanResult(True, "Background cleaned.", background_ratio)
