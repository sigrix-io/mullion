"""Fixtures that build the awkward images by hand.

Every image here is constructed in memory rather than committed as a binary,
so a reader can see exactly what makes each one awkward — which is the whole
point, since the defects this library exists for are invisible in a rendered
picture.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

# The RGB that virtually every encoder writes underneath a fully transparent
# pixel. It is what ``convert("RGB")`` keeps when it drops the alpha channel,
# and therefore the colour of the rectangle that shows up on the page.
BLACK_UNDER_TRANSPARENT = (0, 0, 0)


def as_png(image: Image.Image) -> bytes:
    """Encode ``image`` to PNG bytes, the way an upload would arrive."""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def png_bytes():
    """``as_png`` as a fixture, so test modules need no cross-module import."""
    return as_png


@pytest.fixture
def rgba_cutout() -> Image.Image:
    """A red disc on fully transparent corners, black underneath the alpha.

    This is what a cutout PNG from any design tool looks like: the corner
    pixels are ``(0, 0, 0, 0)`` — invisible, and black the moment the alpha
    channel is discarded.
    """
    image = Image.new("RGBA", (32, 32), (*BLACK_UNDER_TRANSPARENT, 0))
    for x in range(8, 24):
        for y in range(8, 24):
            image.putpixel((x, y), (220, 40, 40, 255))
    return image


@pytest.fixture
def la_cutout() -> Image.Image:
    """Greyscale + alpha. Transparent, and not in ``RGBA``."""
    image = Image.new("LA", (16, 16), (0, 0))
    for x in range(4, 12):
        for y in range(4, 12):
            image.putpixel((x, y), (200, 255))
    return image


@pytest.fixture
def palette_cutout() -> Image.Image:
    """Palette mode carrying transparency in ``info``, not in the mode string.

    Index 0 is black and is declared transparent; index 1 is the subject. This
    is what most "small" PNGs are saved as, and the shape a check written as
    ``image.mode == "RGBA"`` walks straight past.
    """
    image = Image.new("P", (16, 16), 0)
    image.putpalette([0, 0, 0, 40, 90, 200] + [0] * (256 * 3 - 6))
    for x in range(4, 12):
        for y in range(4, 12):
            image.putpixel((x, y), 1)
    image.info["transparency"] = 0
    return image


@pytest.fixture
def sideways_jpeg_bytes() -> bytes:
    """A landscape JPEG carrying the EXIF tag that says "display portrait".

    Orientation 6 means the viewer must rotate 90° clockwise, so a correct
    reader turns these 40x20 stored pixels into a 20x40 image.
    """
    image = Image.new("RGB", (40, 20), (120, 160, 200))
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


#: The off-white a scanner or a phone's auto white balance produces. Both the
#: background and the subject's interior highlight are this colour, which is
#: what makes the fixture below able to tell two implementations apart.
OFF_WHITE = (250, 249, 247)


@pytest.fixture
def product_shot() -> Image.Image:
    """A dark subject on an off-white background, with an off-white hole in it.

    The hole is the case a global brightness threshold gets wrong: it is the
    *same colour* as the background but is enclosed by the subject, so nothing
    connects it to the frame. A correct cleaner leaves it alone.

    It matters that the hole is off-white rather than pure white. Cleaning
    pushes the background to pure white, so a hole that started pure white
    would look identical whether it was cleaned or not — and a test asserting
    it is white would pass against the very implementation it exists to reject.
    """
    image = Image.new("RGB", (40, 40), OFF_WHITE)
    for x in range(8, 32):
        for y in range(8, 32):
            image.putpixel((x, y), (30, 30, 35))
    for x in range(16, 24):
        for y in range(16, 24):
            image.putpixel((x, y), OFF_WHITE)
    return image


@pytest.fixture
def full_bleed_photo() -> Image.Image:
    """No background at all — a mid-tone frame edge to edge."""
    image = Image.new("RGB", (24, 24), (90, 110, 70))
    for x in range(24):
        for y in range(24):
            image.putpixel((x, y), (60 + x * 4, 100, 70 + y * 3))
    return image


@pytest.fixture
def png_path(tmp_path):
    """Write an image to a real file and hand back the path."""

    def _write(image: Image.Image, name: str = "image.png"):
        destination = tmp_path / name
        image.save(destination)
        return destination

    return _write
