"""A mark that has to survive other people's photographs.

The assertions here are deliberately about *where* the ink lands and *that
both* inks land, rather than about exact pixels. The type is drawn with
Pillow's bundled default face, which is a scalable FreeType face from 10.1 and
a fixed bitmap below it — so a test pinning glyph coordinates would pass on one
supported Pillow and fail on another, for a reason that has nothing to do with
this module being correct.

What does not move with the font is the arithmetic: the clamps, which side the
scale is taken from, and which corner the mark goes in.
"""

from __future__ import annotations

import pytest
from PIL import Image

from mullion import DEFAULT_WATERMARK_STYLE, WatermarkStyle, watermark

TEXT = "example.com"


def quadrant_changes(before: Image.Image, after: Image.Image) -> dict[str, int]:
    """How many pixels changed, per quadrant."""
    width, height = before.size
    base = before.convert("RGBA")
    counts = {"top-left": 0, "top-right": 0, "bottom-left": 0, "bottom-right": 0}
    for x in range(width):
        for y in range(height):
            if base.getpixel((x, y)) != after.getpixel((x, y)):
                vertical = "top" if y < height // 2 else "bottom"
                horizontal = "left" if x < width // 2 else "right"
                counts[f"{vertical}-{horizontal}"] += 1
    return counts


@pytest.fixture
def plain() -> Image.Image:
    return Image.new("RGB", (400, 300), (70, 90, 120))


class TestTheMarkLandsWhereItWasAsked:
    def test_something_is_actually_drawn(self, plain):
        """The canary. Every corner assertion below is vacuous without it."""
        assert sum(quadrant_changes(plain, watermark(plain, TEXT)).values()) > 0

    @pytest.mark.parametrize(
        "corner, opposite",
        [
            ("bottom-right", "top-left"),
            ("top-left", "bottom-right"),
            ("top-right", "bottom-left"),
            ("bottom-left", "top-right"),
        ],
    )
    def test_each_corner_is_marked_and_its_opposite_is_not(self, plain, corner, opposite):
        style = WatermarkStyle(corner=corner)
        changes = quadrant_changes(plain, watermark(plain, TEXT, style=style))
        assert changes[corner] > 0
        assert changes[opposite] == 0

    def test_the_default_corner_is_the_bottom_right(self, plain):
        assert DEFAULT_WATERMARK_STYLE.corner == "bottom-right"
        assert quadrant_changes(plain, watermark(plain, TEXT))["bottom-right"] > 0


class TestItSurvivesABrightPicture:
    def test_white_type_alone_would_vanish_on_white(self):
        """The premise: the halo is not decoration.

        A mark drawn only in the light ink is invisible on a bright sky, which
        reads as a rendering fault rather than as a subtle watermark.
        """
        white = Image.new("RGB", (300, 200), (255, 255, 255))
        no_halo = WatermarkStyle(shadow_opacity=0)
        assert sum(quadrant_changes(white, watermark(white, TEXT, style=no_halo)).values()) == 0

    def test_with_the_halo_it_reads(self):
        white = Image.new("RGB", (300, 200), (255, 255, 255))
        assert sum(quadrant_changes(white, watermark(white, TEXT)).values()) > 0

    def test_and_it_still_reads_on_black(self):
        black = Image.new("RGB", (300, 200), (0, 0, 0))
        assert sum(quadrant_changes(black, watermark(black, TEXT)).values()) > 0


class TestTheTypeSize:
    def test_it_is_clamped_at_the_small_end(self):
        """Unclamped, the proportional size is illegible on a thumbnail."""
        style = DEFAULT_WATERMARK_STYLE
        assert style.type_size(120, 90) == style.min_type_px

    def test_it_is_clamped_at_the_large_end(self):
        style = DEFAULT_WATERMARK_STYLE
        assert style.type_size(6000, 4000) == style.max_type_px

    def test_between_the_clamps_it_is_proportional(self):
        assert DEFAULT_WATERMARK_STYLE.type_size(1280, 720) == round(720 * 0.042)

    def test_it_scales_off_the_shorter_side_not_the_width(self):
        """A portrait render and a landscape one get the same visual weight.

        Scaling off the width would make the tall one's mark look stamped on
        by a different tool.
        """
        style = DEFAULT_WATERMARK_STYLE
        assert style.type_size(1280, 720) == style.type_size(720, 1280)

    def test_a_degenerate_size_does_not_divide_by_anything(self):
        assert DEFAULT_WATERMARK_STYLE.type_size(0, 0) == DEFAULT_WATERMARK_STYLE.min_type_px


class TestTheContract:
    def test_the_input_is_never_mutated(self, plain):
        before = plain.tobytes()
        watermark(plain, TEXT)
        assert plain.tobytes() == before
        assert plain.mode == "RGB"

    def test_it_returns_rgba_so_the_caller_can_still_decide(self, plain):
        assert watermark(plain, TEXT).mode == "RGBA"

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_no_text_is_no_mark_rather_than_an_error(self, plain, empty):
        """A configuration that says "do not mark" is not a failure."""
        assert watermark(plain, empty) is plain

    def test_transparency_in_the_picture_is_carried_through(self, rgba_cutout):
        assert watermark(rgba_cutout, TEXT).getpixel((0, 0))[3] == 0

    def test_a_caller_can_bring_their_own_face(self, plain):
        """The escape hatch a brand mark needs, and that the clamps preclude."""
        from PIL import ImageFont

        marked = watermark(plain, TEXT, font=ImageFont.load_default())
        assert sum(quadrant_changes(plain, marked).values()) > 0

    def test_the_style_is_frozen_so_a_shared_default_cannot_be_edited(self):
        with pytest.raises(AttributeError):
            DEFAULT_WATERMARK_STYLE.opacity = 255  # type: ignore[misc]
