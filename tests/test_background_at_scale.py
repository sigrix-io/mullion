"""The flood runs on a downscaled copy, and what that costs.

``ImageDraw.floodfill`` is pure Python, so the flood was the whole cost of this
module — around 1.6 seconds per megapixel, which is 45 seconds on a photo off a
modern phone. Above ``_FLOOD_MAX_EDGE`` the flood now runs on a reduced copy.

Every other fixture in this suite is between 16 and 200 pixels, so none of them
reach that path at all: they would pass identically against a downscale that
ate the subject. Hence this file. What it pins is the trade the downscale
makes — the connectivity answer comes from the small copy, membership stays
full resolution — and the one thing that trade must never break, which is the
enclosed-highlight rule the whole module exists for.

The mechanism tests shrink ``_FLOOD_MAX_EDGE`` instead of growing the fixture.
Same arithmetic, same code path, and a comparison against the full-resolution
mask that costs milliseconds rather than seconds. One test at the real cap
keeps them honest about the default actually engaging.
"""

from __future__ import annotations

from random import Random

import pytest
from PIL import Image, ImageChops, ImageDraw

from mullion import DEFAULT_TOLERANCE, background, clean_background

#: Matches ``conftest``'s ``product_shot``: off-white, not white, so that a hole
#: which was wrongly cleaned is distinguishable from one that was left alone.
OFF_WHITE = (250, 249, 247)
SUBJECT = (30, 30, 35)


def walled_shot(width: int, height: int, *, wall: int) -> Image.Image:
    """A dark subject on off-white, with an off-white hole ``wall`` px inside it.

    The hole is the same colour as the background and is enclosed by the
    subject, so only connectivity — not brightness — can tell them apart.
    ``wall`` is the thickness of the subject between the two, which is exactly
    what a downscale can close.
    """
    image = Image.new("RGB", (width, height), OFF_WHITE)
    draw = ImageDraw.Draw(image)
    inset_x, inset_y = width // 5, height // 5
    draw.rectangle([inset_x, inset_y, width - inset_x, height - inset_y], fill=SUBJECT)
    centre_x, centre_y = width // 2, height // 2
    hole = min(width, height) // 8
    draw.rectangle(
        [centre_x - hole, centre_y - hole, centre_x + hole, centre_y + hole],
        fill=OFF_WHITE,
    )
    assert min(inset_x, inset_y) - hole >= wall, "fixture's wall is thinner than asked for"
    return image


def agreement(one: Image.Image, other: Image.Image) -> float:
    """Fraction of pixels on which two masks say the same thing."""
    differing = sum(ImageChops.difference(one, other).histogram()[1:])
    return 1.0 - differing / (one.size[0] * one.size[1])


def full_resolution_mask(image: Image.Image, monkeypatch) -> Image.Image:
    """The mask this module would build with no downscale at all."""
    monkeypatch.setattr(background, "_FLOOD_MAX_EDGE", 10**9)
    mask, _ = background._background_mask(image.convert("RGB"), tolerance=DEFAULT_TOLERANCE)
    monkeypatch.undo()
    return mask


class TestWhenTheFloodIsDownscaledAtAll:
    def test_an_image_within_the_cap_is_flooded_whole(self):
        assert background._flood_scale((background._FLOOD_MAX_EDGE, 10)) == 1

    def test_the_factor_brings_the_longest_edge_under_the_cap(self):
        for size in [(1025, 10), (4000, 3000), (6000, 4000), (12000, 900)]:
            factor = background._flood_scale(size)
            assert max(size) / factor <= background._FLOOD_MAX_EDGE, size

    def test_the_default_cap_engages_on_a_photograph_sized_image(self, monkeypatch):
        """Not a tautology: it is the assertion that the *default* is reached.

        Every other test here shrinks the cap to keep the fixtures small, so
        without this one a default of, say, 100000 — which would leave the
        45-second flood in place for every real caller — would pass the file.
        """
        flooded: list[tuple[int, int]] = []
        real = background._reached_region

        def spy(candidates):
            flooded.append(candidates.size)
            return real(candidates)

        monkeypatch.setattr(background, "_reached_region", spy)
        image = walled_shot(1100, 800, wall=60)

        cleaned, result = clean_background(image)

        assert result.cleaned
        assert flooded, "the flood never ran"
        # Absolute numbers, not ``_FLOOD_MAX_EDGE``. Comparing the flood's size
        # against the very constant that decided it is a tautology: it was
        # written that way first, and raising the cap to 100000 — restoring the
        # 45-second flood for every real caller — passed. The claim is about
        # pixels, so it has to be spelled in pixels.
        assert flooded[0] != image.size, "flooded at full resolution"
        assert max(flooded[0]) <= 2048, (
            f"flooded at {flooded[0]}: the cap is high enough that a photograph "
            f"is still flooded whole"
        )
        assert cleaned.getpixel((0, 0)) == (255, 255, 255), "the background was not cleaned"
        assert cleaned.getpixel((550, 400)) == OFF_WHITE, "the enclosed hole was eaten"


class TestTheDownscaledMaskAgreesWithTheFullResolutionOne:
    def test_within_a_fraction_of_a_percent(self, monkeypatch):
        image = walled_shot(240, 240, wall=18).convert("RGB")
        expected = full_resolution_mask(image, monkeypatch)

        monkeypatch.setattr(background, "_FLOOD_MAX_EDGE", 60)  # factor 4
        actual, ratio = background._background_mask(image, tolerance=DEFAULT_TOLERANCE)

        assert ratio > 0
        assert agreement(actual, expected) >= 0.99

    def test_at_full_photograph_size_too(self, monkeypatch):
        """The same claim once, without the cap shrunk, on a real-sized image.

        Slower than the rest of the file on purpose: the small-fixture tests
        prove the arithmetic, and this proves the arithmetic is what runs.
        """
        image = walled_shot(1100, 800, wall=60).convert("RGB")
        expected = full_resolution_mask(image, monkeypatch)

        actual, ratio = background._background_mask(image, tolerance=DEFAULT_TOLERANCE)

        assert ratio > 0
        assert agreement(actual, expected) >= 0.99


class TestTheBlockVoteSurvivesANoisyBackground:
    def test_scattered_sub_tolerance_pixels_do_not_disconnect_the_background(self, monkeypatch):
        """Why a block is background on a majority and not on a clean sweep.

        "Every pixel in the block must be a candidate" is the rule that
        preserves a one-pixel wall, and it was written first. A photographed
        background is not clean: JPEG noise scatters sub-tolerance pixels
        through it, and under that rule each one turns its whole block into a
        wall until the background is islands the flood cannot cross. Measured
        against the full-resolution mask on a 3MP shot at 2% noise, the strict
        rule agreed on 83% of pixels at factor 4 and 40% at factor 6; the
        majority vote held at 99.9% everywhere.

        This fixture is the small version of that measurement. It fails
        against the strict rule and passes against the vote.
        """
        image = walled_shot(240, 240, wall=18).convert("RGB")
        noise = Random(7)
        for _ in range(int(240 * 240 * 0.03)):
            x, y = noise.randrange(240), noise.randrange(240)
            if image.getpixel((x, y)) == OFF_WHITE:
                level = noise.randrange(180, 239)
                image.putpixel((x, y), (level, level, level))

        expected = full_resolution_mask(image, monkeypatch)
        monkeypatch.setattr(background, "_FLOOD_MAX_EDGE", 40)  # factor 6
        actual, ratio = background._background_mask(image, tolerance=DEFAULT_TOLERANCE)

        assert ratio > 0
        assert agreement(actual, expected) >= 0.98


class TestTheSubjectSurvivesTheDownscale:
    def test_no_pixel_darker_than_the_tolerance_is_ever_in_the_mask(self, monkeypatch):
        """The guarantee that makes the downscale safe, stated directly.

        A reduced copy says which *blocks* are background; blocks straddle the
        subject's edge, so scaling that answer back up claims subject pixels
        along every boundary. Intersecting it with the full-resolution
        candidates is what takes them away again — the small copy decides
        connectivity, never membership. Drop the intersection and this fails
        while every other test in the suite still passes.
        """
        image = walled_shot(240, 240, wall=18).convert("RGB")
        monkeypatch.setattr(background, "_FLOOD_MAX_EDGE", 40)  # factor 6

        mask, _ = background._background_mask(image, tolerance=DEFAULT_TOLERANCE)

        greyscale = image.convert("L")
        offenders = [
            (x, y)
            for x in range(image.width)
            for y in range(image.height)
            if mask.getpixel((x, y)) and greyscale.getpixel((x, y)) < DEFAULT_TOLERANCE
        ]
        assert offenders == [], f"{len(offenders)} subject pixels were marked background"

    def test_an_enclosed_hole_is_still_unreachable(self, monkeypatch):
        """The property the module exists for, asserted at scale.

        A downscale is exactly the operation that can close the wall between
        the hole and the frame, and once they are connected the hole is cleaned
        and the mug loses its highlight. Measured: the wall survives while it
        is roughly 1.5x the scale factor or thicker, which is what
        ``_FLOOD_MAX_EDGE``'s note records.
        """
        image = walled_shot(240, 240, wall=18)
        monkeypatch.setattr(background, "_FLOOD_MAX_EDGE", 40)  # factor 6, wall 3x that

        cleaned, result = clean_background(image)

        assert result.cleaned, "nothing was cleaned, so the hole proves nothing"
        assert cleaned.getpixel((0, 0)) == (255, 255, 255)
        assert cleaned.getpixel((120, 120)) == OFF_WHITE


class TestTheFallbackToFullResolution:
    def test_a_border_thinner_than_one_block_is_flooded_whole(self, monkeypatch):
        """A near-white frame one pixel wide, on an otherwise dark image.

        The reduced copy votes every border block dark and finds nothing to
        flood, while the full-resolution frame — which is what
        ``looks_like_white_background`` reads — says there is a background
        here. Answering "no background" would be wrong, so the flood is redone
        at full resolution. Rare enough to be worth the cost, and the only path
        in the module that runs the flood twice.
        """
        image = Image.new("RGB", (120, 120), SUBJECT)
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, 119, 119], outline=OFF_WHITE, width=1)

        flooded: list[tuple[int, int]] = []
        real = background._reached_region

        def spy(candidates):
            flooded.append(candidates.size)
            return real(candidates)

        monkeypatch.setattr(background, "_reached_region", spy)
        monkeypatch.setattr(background, "_FLOOD_MAX_EDGE", 20)  # factor 6

        mask, ratio = background._background_mask(image, tolerance=DEFAULT_TOLERANCE)

        assert [size for size in flooded if max(size) > 20] == [(120, 120)], (
            f"expected a full-resolution retry, flooded {flooded}"
        )
        assert ratio > 0, "the one-pixel frame was never found"
        assert mask.getpixel((0, 0)) == 255


@pytest.mark.parametrize("size", [(1, 4000), (4000, 1)])
def test_a_single_pixel_strip_does_not_divide_by_zero(size):
    """``reduce`` floors, so a 1px edge over the cap could reduce to nothing."""
    image = Image.new("RGB", size, OFF_WHITE)

    cleaned, result = clean_background(image)

    assert cleaned.size == size
    assert isinstance(result.cleaned, bool)
