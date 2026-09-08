"""Background cleaning, and the two rules that keep it from eating the subject.

The interior-hole case is the one worth reading first. A global brightness
threshold — the obvious implementation — cannot tell the white *inside* a
subject from the white *around* it, so it removes both and the mug loses its
highlight. Every assertion about the hole below fails against that
implementation and passes against this one, which is the whole reason the flood
fill is seeded from the border.
"""

from __future__ import annotations

import pytest
from PIL import Image

from mullion import (
    DEFAULT_TOLERANCE,
    BackgroundCleanMode,
    background,
    clean_background,
    keeps_alpha,
    looks_like_white_background,
    open_path,
)

# Kept in step with the ``product_shot`` fixture in conftest, which explains why
# the colour has to be off-white rather than pure white.
OFF_WHITE = (250, 249, 247)


class TestOnlyWhatTouchesTheBorderIsCleaned:
    def test_the_near_white_frame_is_cleaned_to_pure_white(self, product_shot):
        assert product_shot.getpixel((0, 0)) == (250, 249, 247), "not pure white to start"
        cleaned, result = clean_background(product_shot)
        assert result.cleaned
        assert cleaned.getpixel((0, 0)) == (255, 255, 255)

    def test_an_enclosed_near_white_region_survives(self, product_shot):
        """The subject's own highlight. Nothing connects it to the frame.

        The assertion is that it is *unchanged*, not that it is light. A global
        threshold would push it to pure white along with the background, which
        is exactly what the inequality below refuses.
        """
        cleaned, _ = clean_background(product_shot, feather=0)
        assert cleaned.getpixel((20, 20)) == OFF_WHITE
        assert cleaned.getpixel((20, 20)) != (255, 255, 255)

    def test_a_global_threshold_would_not_tell_the_two_apart(self, product_shot):
        """States the alternative implementation, so the tests above mean something.

        Both regions are at or above the tolerance, so brightness alone cannot
        separate them; only reachability from the border can.
        """
        assert min(product_shot.getpixel((0, 0))) >= DEFAULT_TOLERANCE
        assert min(product_shot.getpixel((20, 20))) >= DEFAULT_TOLERANCE

    def test_the_subject_is_untouched(self, product_shot):
        cleaned, _ = clean_background(product_shot, feather=0)
        assert cleaned.getpixel((12, 12)) == (30, 30, 35)

    def test_the_reported_ratio_is_the_background_share(self, product_shot):
        # 40x40 with a 24x24 subject: the frame is 1600 - 576 = 1024 px, 64%.
        _, result = clean_background(product_shot)
        assert 0.60 < result.background_ratio < 0.68


class TestAnImageWithNoBackgroundIsLeftAlone:
    def test_a_full_bleed_photo_is_returned_untouched(self, full_bleed_photo):
        cleaned, result = clean_background(full_bleed_photo)
        assert not result.cleaned
        assert cleaned is full_bleed_photo, "returned as-is, not copied and rebuilt"

    def test_the_refusal_says_why(self, full_bleed_photo):
        _, result = clean_background(full_bleed_photo)
        assert "No white background detected" in result.message

    def test_the_verdict_can_be_asked_for_on_its_own(self, product_shot, full_bleed_photo):
        assert looks_like_white_background(product_shot)
        assert not looks_like_white_background(full_bleed_photo)

    def test_one_dark_edge_does_not_disqualify_a_product_shot(self, product_shot):
        """An object running off the frame is ordinary; coverage is a fraction."""
        for y in range(40):
            product_shot.putpixel((0, y), (20, 20, 20))
        assert looks_like_white_background(product_shot)


class TestModes:
    def test_off_returns_the_image_untouched_and_says_so(self, product_shot):
        cleaned, result = clean_background(product_shot, mode="off")
        assert cleaned is product_shot
        assert not result.cleaned
        assert result.background_ratio == 0.0

    def test_transparent_zeroes_the_alpha_instead_of_painting(self, product_shot):
        cleaned, result = clean_background(product_shot, mode="transparent", feather=0)
        assert result.cleaned
        assert cleaned.mode == "RGBA"
        assert cleaned.getpixel((0, 0))[3] == 0
        assert cleaned.getpixel((12, 12))[3] == 255
        assert cleaned.getpixel((20, 20))[3] == 255, "the enclosed highlight is not a hole"

    def test_transparent_subtracts_alpha_rather_than_assigning_it(self):
        """A hole the image already had must stay a hole.

        The subject here is a ring with a transparent centre. That centre is
        enclosed, so it is not in the background mask — and an implementation
        that *assigns* alpha from the inverted mask would hand it back as
        opaque, filling in a hole the author cut deliberately. Subtracting from
        the alpha the image already carries cannot do that.
        """
        image = Image.new("RGBA", (24, 24), (255, 255, 255, 255))
        for x in range(6, 18):
            for y in range(6, 18):
                image.putpixel((x, y), (20, 20, 20, 255))
        for x in range(10, 14):
            for y in range(10, 14):
                image.putpixel((x, y), (0, 0, 0, 0))

        cleaned, result = clean_background(image, mode="transparent", feather=0)

        assert result.cleaned
        assert cleaned.getpixel((0, 0))[3] == 0, "the white border became transparent"
        assert cleaned.getpixel((12, 12))[3] == 0, "the hole the image already had"
        assert cleaned.getpixel((7, 7))[3] == 255, "the subject is opaque"

    def test_flatten_uses_the_callers_matte(self, product_shot):
        charcoal = (18, 18, 22)
        cleaned, _ = clean_background(product_shot, feather=0, matte=charcoal)
        assert cleaned.getpixel((0, 0)) == charcoal

    def test_a_string_is_accepted_wherever_the_enum_is(self, product_shot):
        from_string, _ = clean_background(product_shot, mode="flatten")
        from_enum, _ = clean_background(product_shot, mode=BackgroundCleanMode.FLATTEN)
        assert from_string.tobytes() == from_enum.tobytes()

    def test_an_unknown_mode_is_refused_rather_than_coerced(self, product_shot):
        with pytest.raises(ValueError):
            clean_background(product_shot, mode="erase")


class TestKeepsAlpha:
    def test_only_transparent_needs_the_source_alpha(self):
        assert keeps_alpha("transparent")
        assert not keeps_alpha("flatten")
        assert not keeps_alpha("off")

    def test_it_is_the_rule_the_open_call_should_read(self, tmp_path):
        """The coupling this helper exists to name, shown both ways.

        Opened without ``keep_alpha``, an existing cutout is flattened onto
        white *before* cleaning, so its anti-aliased edge keeps the white it
        was blended with. Opened with it, the edge survives as partial alpha.
        """
        source = Image.new("RGBA", (24, 24), (255, 255, 255, 0))
        for x in range(8, 16):
            for y in range(8, 16):
                image_alpha = 128 if x == 8 else 255
                source.putpixel((x, y), (200, 40, 40, image_alpha))
        path = tmp_path / "cutout.png"
        source.save(path)

        mode = "transparent"
        careless = open_path(path)
        careful = open_path(path, keep_alpha=keeps_alpha(mode))

        assert careless.mode == "RGB", "the alpha is already gone"
        assert careful.mode == "RGBA"

        cleaned, _ = clean_background(careful, mode=mode, feather=0)
        assert cleaned.getpixel((8, 12))[3] == 128, "the soft edge survived"


class TestArgumentValidation:
    @pytest.mark.parametrize("tolerance", [-1, 256])
    def test_tolerance_outside_the_channel_range_is_refused(self, product_shot, tolerance):
        with pytest.raises(ValueError, match="tolerance"):
            clean_background(product_shot, tolerance=tolerance)

    def test_a_negative_feather_is_refused(self, product_shot):
        with pytest.raises(ValueError, match="feather"):
            clean_background(product_shot, feather=-1)

    def test_a_zero_sized_image_has_no_border_to_read(self):
        assert not looks_like_white_background(Image.new("RGB", (0, 0)))


class TestResultReporting:
    def test_a_clean_pass_reports_the_share_it_touched(self, product_shot):
        _, result = clean_background(product_shot)
        assert result.message.startswith("Cleaned background (")
        assert "%" in result.message

    def test_the_result_is_immutable(self, product_shot):
        _, result = clean_background(product_shot)
        with pytest.raises(Exception):  # noqa: B017 - frozen dataclass raises FrozenInstanceError
            result.cleaned = False


class TestPixelAccessNarrowing:
    """The mode assumptions that make the annotations true (#3).

    ``py.typed`` ships in the wheel, so these annotations are a promise to
    every consumer's type checker rather than a note to ourselves. What a
    subscript on ``Image.load()`` yields depends on the image's mode, and both
    loaders below claim one — so the claim is asserted at runtime, not trusted.
    A ``# type: ignore`` here would have silenced the checker without recording
    what it was silenced for, and without failing when the assumption stopped
    holding.
    """

    def test_the_rgb_loader_refuses_an_image_that_is_not_rgb(self):
        with pytest.raises(ValueError, match="expected an RGB image"):
            background._rgb_pixels(Image.new("L", (4, 4)))

    def test_the_grey_loader_refuses_an_image_that_is_not_grey(self):
        with pytest.raises(ValueError, match="expected an L image"):
            background._grey_pixels(Image.new("RGB", (4, 4)))

    def test_the_rgb_loader_yields_the_triple_its_type_promises(self):
        pixels = background._rgb_pixels(Image.new("RGB", (4, 4), (12, 34, 56)))
        assert pixels[0, 0] == (12, 34, 56)

    def test_the_grey_loader_yields_the_level_its_type_promises(self):
        pixels = background._grey_pixels(Image.new("L", (4, 4), 200))
        assert pixels[0, 0] == 200

    def test_the_border_reader_only_accepts_what_makes_its_return_type_true(self):
        """``_border_pixels`` is annotated ``list[tuple[int, int, int]]``.

        That is only true of an RGB image, and its one caller converts before
        calling. Nothing but this assertion stops a second caller skipping the
        conversion and getting bare levels back under an annotation promising
        triples.
        """
        with pytest.raises(ValueError, match="expected an RGB image"):
            background._border_pixels(Image.new("L", (4, 4)))
