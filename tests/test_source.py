"""The one correct open, proved against the three transparency shapes.

Each test states the wrong answer alongside the right one. That is deliberate:
a test asserting only that the corner is white passes just as happily against a
library that never looked at the alpha channel at all, because a white image
has white corners. Showing that ``convert("RGB")`` really does produce black
here is what makes the assertion mean something.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from mullion import (
    WHITE,
    flatten_onto,
    has_transparency,
    normalize,
    open_bytes,
    open_path,
)


class TestTransparencyIsResolvedNotDropped:
    def test_a_bare_convert_really_does_produce_black(self, rgba_cutout):
        """The premise. Without this the assertions below prove nothing."""
        assert rgba_cutout.convert("RGB").getpixel((0, 0)) == (0, 0, 0)

    def test_rgba_corners_become_the_matte(self, rgba_cutout):
        assert normalize(rgba_cutout).getpixel((0, 0)) == WHITE

    def test_greyscale_alpha_corners_become_the_matte(self, la_cutout):
        assert normalize(la_cutout).getpixel((0, 0)) == WHITE

    def test_palette_transparency_is_seen_even_though_the_mode_is_not_rgba(self, palette_cutout):
        """The shape a ``mode == "RGBA"`` check walks past."""
        assert palette_cutout.mode == "P"
        assert palette_cutout.convert("RGB").getpixel((0, 0)) == (0, 0, 0)
        assert normalize(palette_cutout).getpixel((0, 0)) == WHITE

    def test_the_subject_is_untouched(self, rgba_cutout):
        assert normalize(rgba_cutout).getpixel((16, 16)) == (220, 40, 40)

    def test_the_matte_is_the_callers_choice(self, rgba_cutout):
        charcoal = (18, 18, 22)
        assert normalize(rgba_cutout, matte=charcoal).getpixel((0, 0)) == charcoal

    def test_keep_alpha_preserves_the_channel_rather_than_compositing(self, rgba_cutout):
        kept = normalize(rgba_cutout, keep_alpha=True)
        assert kept.mode == "RGBA"
        assert kept.getpixel((0, 0))[3] == 0

    def test_keep_alpha_promotes_palette_transparency_to_a_real_channel(self, palette_cutout):
        kept = normalize(palette_cutout, keep_alpha=True)
        assert kept.mode == "RGBA"
        assert kept.getpixel((0, 0))[3] == 0

    def test_an_opaque_image_is_returned_in_the_requested_mode(self):
        opaque = Image.new("RGB", (4, 4), (10, 20, 30))
        assert normalize(opaque).mode == "RGB"
        assert normalize(opaque, keep_alpha=True).mode == "RGBA"

    def test_the_input_is_never_mutated(self, rgba_cutout):
        before = rgba_cutout.getpixel((0, 0))
        normalize(rgba_cutout)
        assert rgba_cutout.getpixel((0, 0)) == before
        assert rgba_cutout.mode == "RGBA"


class TestHasTransparency:
    def test_it_reads_all_three_shapes(self, rgba_cutout, la_cutout, palette_cutout):
        assert has_transparency(rgba_cutout)
        assert has_transparency(la_cutout)
        assert has_transparency(palette_cutout)

    def test_a_palette_image_without_the_info_key_is_opaque(self, palette_cutout):
        """``P`` alone is not transparency — the key in ``info`` is."""
        del palette_cutout.info["transparency"]
        assert not has_transparency(palette_cutout)

    def test_plain_modes_are_opaque(self):
        assert not has_transparency(Image.new("RGB", (2, 2)))
        assert not has_transparency(Image.new("L", (2, 2)))


class TestFlattenOnto:
    def test_it_is_safe_to_call_on_an_opaque_image(self):
        opaque = Image.new("RGB", (2, 2), (1, 2, 3))
        assert flatten_onto(opaque).getpixel((0, 0)) == (1, 2, 3)

    def test_partial_alpha_is_blended_rather_than_snapped(self):
        """A half-transparent red over white is pink, not red and not white."""
        half = Image.new("RGBA", (2, 2), (255, 0, 0, 128))
        red, green, blue = flatten_onto(half).getpixel((0, 0))
        assert red == 255
        assert 120 < green < 140
        assert 120 < blue < 140


class TestOrientation:
    def test_the_exif_tag_is_applied(self, sideways_jpeg_bytes):
        stored = Image.open(BytesIO(sideways_jpeg_bytes))
        assert stored.size == (40, 20), "the file really is stored landscape"
        assert open_bytes(sideways_jpeg_bytes).size == (20, 40)

    def test_the_tag_is_consumed_not_merely_applied(self, sideways_jpeg_bytes):
        """A surviving tag would be applied twice by the next reader."""
        upright = open_bytes(sideways_jpeg_bytes)
        assert 0x0112 not in upright.getexif()

    def test_an_image_with_no_tag_is_left_alone(self):
        plain = Image.new("RGB", (8, 4), (5, 5, 5))
        assert normalize(plain).size == (8, 4)


class TestAdapters:
    def test_bytes_and_path_agree(self, rgba_cutout, png_path, png_bytes):
        from_path = open_path(png_path(rgba_cutout))
        from_bytes = open_bytes(png_bytes(rgba_cutout))
        assert from_path.tobytes() == from_bytes.tobytes()

    def test_open_path_accepts_a_string_as_well_as_a_pathlike(self, rgba_cutout, png_path):
        path = png_path(rgba_cutout)
        assert open_path(str(path)).size == open_path(path).size

    def test_open_bytes_accepts_a_memoryview(self, rgba_cutout, png_bytes):
        data = png_bytes(rgba_cutout)
        assert open_bytes(memoryview(data)).getpixel((0, 0)) == WHITE

    def test_the_returned_image_outlives_the_closed_file(self, rgba_cutout, png_path):
        """The file handle is closed before the adapter returns.

        A lazily-loaded image would raise here rather than answer, which is why
        :func:`normalize` converts unconditionally instead of handing back an
        untouched opaque image.
        """
        path = png_path(rgba_cutout)
        image = open_path(path)
        path.unlink()
        assert image.getpixel((16, 16)) == (220, 40, 40)

    def test_unreadable_data_raises_rather_than_returning_something(self):
        with pytest.raises(Exception):  # noqa: B017 - Pillow's own type is not part of the contract
            open_bytes(b"this is not an image")
