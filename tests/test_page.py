"""Page geometry: the pixels and the DPI travel together, or they disagree."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from mullion import (
    DEFAULT_DPI,
    NAMED_PAGE_SIZES_MM,
    named_page_geometry,
    resolve_page_geometry,
    to_pixels,
    validate_dpi,
)


class TestUnitConversion:
    def test_inches_scale_with_dpi(self):
        assert to_pixels(10, "in", 300) == 3000
        assert to_pixels(10, "in", 72) == 720

    def test_millimetres_go_through_the_inch(self):
        assert to_pixels(25.4, "mm", 300) == 300

    def test_pixels_pass_through_and_ignore_dpi(self):
        assert to_pixels(1234, "px", 300) == 1234
        assert to_pixels(1234, "px", 72) == 1234

    def test_a_non_integer_result_is_rounded(self):
        # A4's 210 mm is 2480.31... px at 300 DPI.
        assert to_pixels(210, "mm", 300) == 2480

    @pytest.mark.parametrize("value", [0, -1])
    def test_a_non_positive_dimension_is_refused(self, value):
        with pytest.raises(ValueError, match="greater than zero"):
            to_pixels(value, "in", 300)

    def test_a_dimension_that_rounds_to_nothing_is_refused(self):
        """0.001 in at 72 DPI is 0.07 px. Silently returning 0 would 500 later."""
        with pytest.raises(ValueError, match="rounded to zero"):
            to_pixels(0.001, "in", 72)

    def test_an_unknown_unit_names_the_supported_ones(self):
        with pytest.raises(ValueError, match="px', 'in' or 'mm"):
            to_pixels(1, "cm", 300)


class TestNamedPages:
    def test_a4_at_300_is_the_familiar_number(self):
        page = named_page_geometry("a4", dpi=300)
        assert (page.width_px, page.height_px) == (2480, 3508)

    def test_the_name_is_case_and_space_insensitive(self):
        assert named_page_geometry("  LETTER ").width_px == named_page_geometry("letter").width_px

    def test_an_unknown_name_lists_what_is_supported(self):
        with pytest.raises(ValueError) as excinfo:
            named_page_geometry("foolscap")
        for name in NAMED_PAGE_SIZES_MM:
            assert name in str(excinfo.value)

    @pytest.mark.parametrize("name", sorted(NAMED_PAGE_SIZES_MM))
    def test_every_named_size_resolves(self, name):
        page = named_page_geometry(name)
        assert page.width_px > 0 and page.height_px > 0
        assert page.dpi == DEFAULT_DPI


class TestGeometryCarriesItsOwnDpi:
    def test_the_inches_read_back(self):
        page = resolve_page_geometry(page_width=8, page_height=10, unit="in", dpi=300)
        assert (page.width_px, page.height_px) == (2400, 3000)
        assert page.width_inches == 8
        assert page.height_inches == 10

    def test_the_description_states_both(self):
        assert named_page_geometry("a4", dpi=300).description == (
            "2480x3508px (8.27x11.69in at 300 DPI)"
        )

    def test_pixels_and_dpi_cannot_be_set_apart(self):
        """The two numbers are one value, which is the point of the dataclass."""
        page = named_page_geometry("a4", dpi=300)
        with pytest.raises(Exception):  # noqa: B017 - frozen dataclass
            page.dpi = 72


class TestDpiValidation:
    @pytest.mark.parametrize("dpi", [0, -300])
    def test_a_non_positive_dpi_is_refused(self, dpi):
        with pytest.raises(ValueError, match="greater than zero"):
            validate_dpi(dpi)

    def test_an_absurd_dpi_is_refused(self):
        with pytest.raises(ValueError, match="1200"):
            validate_dpi(4800)

    def test_resolving_validates_before_doing_the_arithmetic(self):
        with pytest.raises(ValueError):
            resolve_page_geometry(page_width=1, page_height=1, unit="in", dpi=0)


class TestTheDpiSurvivesTheEncoder:
    """The reason any of this exists: the number has to reach the file."""

    def test_a_png_reads_back_at_the_stated_resolution(self, tmp_path):
        page = resolve_page_geometry(page_width=2, page_height=3, unit="in", dpi=300)
        canvas = Image.new("RGB", (page.width_px, page.height_px), "white")
        destination = tmp_path / "page.png"
        canvas.save(destination, dpi=(page.dpi, page.dpi))

        with Image.open(destination) as written:
            horizontal, vertical = written.info["dpi"]

        # PNG stores pixels per *metre* as an integer, so 300 round-trips as
        # 299.9994. Comparing for equality here is the mistake this note exists
        # to prevent.
        assert horizontal == pytest.approx(300, abs=0.01)
        assert vertical == pytest.approx(300, abs=0.01)

    def test_a_jpeg_reads_back_exactly(self):
        page = resolve_page_geometry(page_width=1, page_height=1, unit="in", dpi=300)
        canvas = Image.new("RGB", (page.width_px, page.height_px), "white")
        buffer = BytesIO()
        canvas.save(buffer, format="JPEG", dpi=(page.dpi, page.dpi))
        buffer.seek(0)

        with Image.open(buffer) as written:
            assert written.info["dpi"] == (300, 300)
