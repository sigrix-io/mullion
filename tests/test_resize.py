"""Two operations, named for what they do to the content.

Each test below states the spelling it exists to replace. A test asserting
only that ``contain`` returns something no larger than the box would pass
against ``thumbnail`` itself — including the part where ``thumbnail`` hands
back ``None`` and edits the caller's image underneath them.
"""

from __future__ import annotations

import pytest
from PIL import Image

from mullion import contain, cover


@pytest.fixture
def landscape() -> Image.Image:
    """800x600 with a gradient, so a resize cannot be mistaken for a fill."""
    image = Image.new("RGB", (800, 600))
    for x in range(0, 800, 8):
        for y in range(0, 600, 8):
            image.paste((x % 256, y % 256, (x + y) % 256), (x, y, x + 8, y + 8))
    return image


class TestContainReplacesThumbnail:
    def test_thumbnail_really_does_return_none_and_mutate(self, landscape):
        """The premise. Without it the two assertions below prove nothing."""
        returned = landscape.thumbnail((100, 100), Image.Resampling.LANCZOS)
        assert returned is None
        assert landscape.size == (100, 75)

    def test_it_returns_the_image_rather_than_none(self, landscape):
        assert contain(landscape, (100, 100)).size == (100, 75)

    def test_the_input_is_left_alone(self, landscape):
        contain(landscape, (100, 100))
        assert landscape.size == (800, 600)

    def test_the_pixels_are_pillows_own(self, landscape):
        """A move, not a reimplementation: same pre-pass, same output.

        ``thumbnail`` runs a reducing-gap pass before the resample. Arithmetic
        plus ``resize`` produces a *similar* picture and different bytes, which
        would make this an upgrade nobody asked for rather than a rename — and
        for a consumer moving onto this call, a silent re-render of every
        cached derivative it has.

        **The box is load-bearing.** That pre-pass only engages past roughly a
        fourfold reduction, so at 800x600 into (320, 320) the two agree to the
        byte and this test passes against either implementation. It was written
        that way first and a mutation walked straight through it. The second
        half is the canary: it fails if the box stops being one that can tell
        the two apart.
        """
        expected = landscape.copy()
        expected.thumbnail((100, 100), Image.Resampling.LANCZOS)
        assert contain(landscape, (100, 100)).tobytes() == expected.tobytes()

        scale = min(100 / landscape.width, 100 / landscape.height)
        naive = landscape.resize(
            (round(landscape.width * scale), round(landscape.height * scale)),
            Image.Resampling.LANCZOS,
        )
        assert naive.size == expected.size
        assert naive.tobytes() != expected.tobytes(), (
            "arithmetic and resize agree with thumbnail at this box, so the "
            "assertion above would pass against either — pick a box with a "
            "larger reduction"
        )


class TestContainDoesNotUpscaleUnlessAsked:
    def test_resize_really_does_upscale(self):
        """``resize`` has no opinion, which is the trap under "no bigger than"."""
        small = Image.new("RGB", (40, 30), (10, 20, 30))
        assert small.resize((400, 300)).size == (400, 300)

    def test_an_image_already_inside_the_box_keeps_its_own_size(self):
        small = Image.new("RGB", (40, 30), (10, 20, 30))
        assert contain(small, (400, 400)).size == (40, 30)

    def test_upscale_fills_the_box_on_its_long_side(self):
        small = Image.new("RGB", (40, 30), (10, 20, 30))
        assert contain(small, (400, 400), upscale=True).size == (400, 300)


class TestCoverFillsAndCrops:
    def test_contain_does_not_fill_the_box(self, landscape):
        """The difference between the two, stated before it is relied on."""
        assert contain(landscape, (200, 200)).size != (200, 200)

    def test_cover_is_exactly_the_box(self, landscape):
        assert cover(landscape, (200, 200)).size == (200, 200)

    def test_it_is_pillows_own_fit(self, landscape):
        from PIL import ImageOps

        expected = ImageOps.fit(
            landscape, (200, 200), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
        assert cover(landscape, (200, 200)).tobytes() == expected.tobytes()

    def test_centering_decides_what_survives_the_crop(self):
        """A band at the top is kept or cut depending on where the caller looks."""
        striped = Image.new("RGB", (100, 300), (20, 20, 20))
        striped.paste((240, 30, 30), (0, 0, 100, 60))

        from_the_top = cover(striped, (100, 100), centering=(0.5, 0.0))
        from_the_middle = cover(striped, (100, 100), centering=(0.5, 0.5))

        assert from_the_top.getpixel((50, 5))[0] > 200
        assert from_the_middle.getpixel((50, 5))[0] < 60


class TestTheAwkwardInputs:
    def test_an_alpha_channel_survives_the_resize(self, rgba_cutout):
        """A resize that quietly returned RGB would undo the open (#5859's bug)."""
        assert contain(rgba_cutout, (16, 16)).mode == "RGBA"

    def test_a_palette_image_is_not_converted_behind_the_callers_back(self, palette_cutout):
        assert contain(palette_cutout, (8, 8)).mode == "P"

    @pytest.mark.parametrize("box", [(0, 100), (100, 0), (-5, 10)])
    def test_a_box_with_no_area_is_refused_rather_than_guessed_at(self, box, landscape):
        with pytest.raises(ValueError, match="greater than zero"):
            contain(landscape, box)
        with pytest.raises(ValueError, match="greater than zero"):
            cover(landscape, box)
