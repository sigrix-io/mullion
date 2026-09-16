"""The black rectangle, waiting on the way out.

``mullion.source`` exists because ``Image.open(...).convert("RGB")`` composites
a cutout onto black. The encoder is where that same line gets written a second
time, by someone who is not making a transparency decision at all — they are
getting rid of ``cannot write mode RGBA as JPEG``.

So the premise tests here matter more than usual. An assertion that the corner
comes out white passes just as happily against a library that never looked at
the alpha channel, because most pictures are not transparent in the corner.
Showing the failure first is what makes the fix mean something.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from mullion import WHITE, encode, supports_alpha


def decode(payload: bytes) -> Image.Image:
    return Image.open(BytesIO(payload))


def near(pixel: tuple[int, ...], colour: tuple[int, ...], tolerance: int = 12) -> bool:
    """Is ``pixel`` that colour, allowing for a lossy encoder?

    Stated once here rather than as a magic number at each call. JPEG moves
    every value a little and moves it most beside a hard edge, which is
    exactly where a flattened cutout puts one — so an equality assertion on a
    decoded JPEG fails for reasons that have nothing to do with the matte.
    """
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, colour, strict=False))


class TestTheFailureThisReplaces:
    def test_an_rgba_image_really_is_refused_by_the_jpeg_encoder(self, rgba_cutout):
        with pytest.raises(OSError, match="cannot write mode RGBA as JPEG"):
            rgba_cutout.save(BytesIO(), format="JPEG")

    def test_and_the_obvious_repair_really_does_blacken_it(self, rgba_cutout):
        """``.convert("RGB")`` silences the error and restores the defect.

        JPEG is lossy, so "black" arrives within a step or two of it; the
        assertion is a neighbourhood rather than an equality for that reason
        and no other.
        """
        buffer = BytesIO()
        rgba_cutout.convert("RGB").save(buffer, format="JPEG", quality=95)
        assert all(channel < 8 for channel in decode(buffer.getvalue()).getpixel((0, 0)))

    def test_encode_composites_instead(self, rgba_cutout):
        corner = decode(encode(rgba_cutout, "JPEG", quality=95)).getpixel((0, 0))
        assert near(corner, WHITE), corner

    def test_the_subject_is_not_touched_on_the_way(self, rgba_cutout):
        """Flattening the background is not licence to repaint the picture."""
        middle = decode(encode(rgba_cutout, "JPEG", quality=95)).getpixel((16, 16))
        assert middle[0] > 180 and middle[1] < 90


class TestWhatTheFormatCanHold:
    def test_a_format_that_carries_alpha_keeps_it(self, rgba_cutout):
        assert decode(encode(rgba_cutout, "PNG")).mode == "RGBA"
        assert decode(encode(rgba_cutout, "PNG")).getpixel((0, 0))[3] == 0

    def test_the_matte_is_the_callers_choice(self, rgba_cutout):
        corner = decode(encode(rgba_cutout, "JPEG", quality=100, matte=(12, 34, 56))).getpixel(
            (0, 0)
        )
        assert near(corner, (12, 34, 56)), corner

    def test_the_palette_shape_is_seen_too(self, palette_cutout):
        """Transparency in ``info`` rather than in the mode string.

        This is the shape that survives a ``mode == "RGBA"`` guard and reaches
        the encoder anyway — and P-mode does not raise on the way to JPEG, so
        there is no error here to provoke the bad repair. It just comes out
        black.
        """
        naive = BytesIO()
        palette_cutout.convert("RGB").save(naive, format="JPEG", quality=95)
        assert all(channel < 8 for channel in decode(naive.getvalue()).getpixel((0, 0)))

        corner = decode(encode(palette_cutout, "JPEG", quality=95)).getpixel((0, 0))
        assert near(corner, WHITE), corner

    def test_an_opaque_image_is_unaffected_either_way(self):
        opaque = Image.new("RGB", (8, 8), (90, 120, 160))
        assert decode(encode(opaque, "JPEG", quality=95)).getpixel((4, 4))[2] > 140


class TestSupportsAlphaIsAskedOfPillow:
    def test_the_two_that_never_move(self):
        """PNG has carried alpha since before Pillow; JPEG never will."""
        assert supports_alpha("PNG") is True
        assert supports_alpha("JPEG") is False

    def test_it_is_case_insensitive_like_pillows_own_save(self):
        assert supports_alpha("png") is supports_alpha("PNG")

    def test_an_unknown_format_answers_no_rather_than_raising(self):
        assert supports_alpha("NOT-A-FORMAT") is False

    def test_and_encode_then_lets_pillow_name_the_real_problem(self, rgba_cutout):
        """The flatten must not swallow the format error or rename it."""
        with pytest.raises(KeyError, match="NOT-A-FORMAT"):
            encode(rgba_cutout, "NOT-A-FORMAT")

    def test_the_probe_tracks_the_installed_pillow_rather_than_a_table(self):
        """Why this is derived, in one assertion.

        AVIF is a plugin and BMP's alpha support arrived in a later Pillow, so
        the right answer for both differs between the versions this library
        supports. A list in the source would be wrong on one of them; asking
        the encoder is right on all of them. This asserts only that the
        question is answerable, which is what the derivation buys.
        """
        assert supports_alpha("AVIF") in (True, False)
        assert supports_alpha("BMP") in (True, False)

    def test_one_bit_of_alpha_still_counts_as_alpha(self):
        """GIF says yes and means something weaker, which the docstring says.

        Pinned because it is the one answer likely to surprise: a soft edge
        encoded to GIF is snapped to on-or-off rather than composited, and a
        caller who needs it composited should flatten deliberately.
        """
        assert supports_alpha("GIF") is True


class TestTheEncodeItself:
    def test_save_options_reach_pillow(self):
        picture = Image.new("RGB", (64, 64))
        for x in range(64):
            for y in range(64):
                picture.putpixel((x, y), (x * 4 % 256, y * 4 % 256, (x * y) % 256))
        assert len(encode(picture, "JPEG", quality=10)) < len(encode(picture, "JPEG", quality=95))

    def test_it_returns_bytes_rather_than_a_buffer(self, rgba_cutout):
        assert isinstance(encode(rgba_cutout, "PNG"), bytes)

    def test_the_input_is_never_mutated(self, rgba_cutout):
        before = rgba_cutout.tobytes()
        encode(rgba_cutout, "JPEG", quality=80)
        assert rgba_cutout.tobytes() == before
        assert rgba_cutout.mode == "RGBA"

    def test_the_default_matte_is_the_libraries_one(self, rgba_cutout):
        assert decode(encode(rgba_cutout, "PNG")).getpixel((0, 0))[3] == 0
        flattened = decode(encode(rgba_cutout, "JPEG", quality=100)).getpixel((0, 0))
        assert near(flattened, WHITE)
