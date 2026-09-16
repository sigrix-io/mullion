"""A discreet text mark, sized against the picture rather than the pixel grid.

A watermark is easy to draw and easy to get wrong in ways that only show up
across a range of real images rather than on the one you tested with:

**A fixed type size is illegible on one image and a billboard on the next.**
14px reads fine on a 480px thumbnail and vanishes on a 4000px render. Scaling
the type proportionally fixes that and introduces the opposite failure at the
extremes, so the size here is proportional *with clamps at both ends*.

**Scaling off the width alone re-weights every portrait image.** A tall render
and a wide one with the same area get marks of visibly different size, and the
tall one looks like it was stamped by a different tool. The scale is taken off
the shorter side, which is stable across both.

**White type disappears into a bright sky.** Which reads as a rendering fault
rather than a subtle mark, and is the single most likely way for this to look
broken on somebody's photograph. The type is drawn over a soft offset halo in
the opposite ink, which costs nothing on a dark image and rescues a bright one.

What this does *not* do is decide policy. It draws a mark and returns the
image; whether a failure here should take the picture down or ship it unmarked
is the application's call, and it is usually the second — these are marketing
images, not access control, and a font fault that failed the request would take
out every picture on the page rather than one mark.

The mark is deliberately not a defacement: one corner, sized against the image,
partly transparent. Covering the picture protects it by making it worthless.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL.Image import Image as PILImage
    from PIL.ImageFont import FreeTypeFont, ImageFont

    AnyFont = FreeTypeFont | ImageFont

__all__ = [
    "DEFAULT_WATERMARK_STYLE",
    "Corner",
    "WatermarkStyle",
    "watermark",
]

#: Which corner the mark sits in.
Corner = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


@dataclass(frozen=True, slots=True)
class WatermarkStyle:
    """Everything about how the mark looks, with the defaults measured on real renders.

    The defaults are a working set rather than a law — they are what a brand
    mark on a photographic render wants, and they are pre-1.0, so they may
    move. Build your own and pass it if you need the mark to sit differently;
    the changelog is where a default moving will be visible.
    """

    #: Type height as a fraction of the image's **shorter** side.
    type_scale: float = 0.042
    #: Floor and ceiling for that, in pixels. Without them a proportional size
    #: is unreadable on a thumbnail and absurd on a large render.
    min_type_px: int = 13
    max_type_px: int = 44
    #: Inset from the corner, again as a fraction of the shorter side.
    margin_scale: float = 0.030
    min_margin_px: int = 6
    #: The type, and how much of it. 255 is a defacement; this is a mark.
    color: tuple[int, int, int] = (255, 255, 255)
    opacity: int = 168
    #: The halo under it, offset as a fraction of the type size.
    shadow_color: tuple[int, int, int] = (0, 0, 0)
    shadow_opacity: int = 92
    shadow_offset_scale: float = 0.055
    corner: Corner = "bottom-right"

    def type_size(self, width: int, height: int) -> int:
        """Type height in px for an image this size, clamped at both ends.

        Public because the clamps are the interesting part: a caller deciding
        whether an image is large enough to be worth marking at all wants the
        same answer this uses, not a second copy of the arithmetic.
        """
        short_side = max(1, min(int(width), int(height)))
        return int(
            max(self.min_type_px, min(self.max_type_px, round(short_side * self.type_scale)))
        )


#: The defaults above, as one importable value.
DEFAULT_WATERMARK_STYLE = WatermarkStyle()


def _load_font(size_px: int) -> AnyFont:
    """Pillow's bundled scalable default, at ``size_px``.

    Deliberately not a path to a system font. A library cannot know what is
    installed where it runs, and a missing ``.ttf`` would fail on somebody
    else's deploy and nowhere near here. ``load_default(size=...)`` has
    returned a scalable FreeType face since Pillow 10.1; below that the
    unsized bitmap default still renders something legible, which is why the
    fallback is a fallback rather than a refusal.
    """
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:  # pragma: no cover - Pillow < 10.1
        return ImageFont.load_default()


def watermark(
    image: PILImage | Any,
    text: str,
    *,
    style: WatermarkStyle = DEFAULT_WATERMARK_STYLE,
    font: AnyFont | None = None,
) -> PILImage:
    """Return ``image`` with ``text`` composited into one corner, in ``RGBA``.

    Takes and returns a Pillow image rather than bytes, so the mark can go on
    between resize and encode — marking before the resize resamples the type
    along with the picture and softens it, and marking after the encode means
    decoding the output again::

        marked = watermark(contain(shot, (1280, 720)), "example.com")
        body = encode(marked, "JPEG", quality=88)

    ``encode`` is what resolves the ``RGBA`` this returns for a format that
    cannot carry it. Empty or whitespace ``text`` returns the image unchanged
    rather than raising: "no mark" is a legitimate thing for a caller's
    configuration to say.

    Passing ``font`` overrides the type size entirely — the style's scale and
    clamps are what size the bundled default, and a caller who has brought
    their own face has already decided how big it is.

    The input is not mutated. The mark is drawn on its own transparent layer
    and alpha-composited, which is what lets the type carry a halo without
    punching a hard-edged box into the picture.
    """
    from PIL import Image, ImageDraw

    cleaned = str(text or "").strip()
    if not cleaned:
        return image

    base = image.convert("RGBA")
    width, height = base.size
    short_side = max(1, min(width, height))

    size_px = style.type_size(width, height)
    face = font if font is not None else _load_font(size_px)
    margin = max(style.min_margin_px, int(round(short_side * style.margin_scale)))
    shadow_offset = max(1, int(round(size_px * style.shadow_offset_scale)))

    layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)

    # Measure through the font rather than assuming. ``textbbox`` accounts for
    # the face's own bearings, so a string with no descender is not left
    # floating above the margin it was supposed to sit on, and the offsets are
    # subtracted back out below so the *ink* lands on the margin.
    left, top, right, bottom = draw.textbbox((0, 0), cleaned, font=face)
    text_width = right - left
    text_height = bottom - top

    top_edge = style.corner.startswith("top")
    left_edge = style.corner.endswith("left")
    x = (margin if left_edge else width - margin - text_width) - left
    y = (margin if top_edge else height - margin - text_height) - top

    draw.text(
        (x + shadow_offset, y + shadow_offset),
        cleaned,
        font=face,
        fill=(*style.shadow_color, style.shadow_opacity),
    )
    draw.text((x, y), cleaned, font=face, fill=(*style.color, style.opacity))

    return Image.alpha_composite(base, layer)
