"""Mullion — get an image in correctly, and back out again.

A mullion is the upright that divides a window into panes: one stone member,
every pane set against it. The name is the point of the library. Every
application that accepts user images opens them somewhere, and if it opens them
in six places it gets six different answers — which is not a hypothesis.
Measured across one real codebase, the same transparent PNG came back on a
**black** rectangle through three upload paths and correctly through four
others, because each had reached for ``Image.open(...).convert("RGB")``
independently.

Nothing about that failure is loud. The response is a 200, the picture renders,
the layout is right. It is only *wrong*, in a way a status-code test cannot see
and a reviewer looking at one image at a time will not catch.

So this library is deliberately small, and does the handful of things that keep
coming back. On the way in:

:mod:`mullion.source`
    One correct open — EXIF orientation applied, transparency resolved rather
    than dropped — with adapters for the two things callers actually hold:
    ``bytes`` from object storage and a filesystem path.

On the way through:

:mod:`mullion.resize`
    :func:`contain` and :func:`cover`, named for what they do to the content,
    because Pillow's three spellings do not agree: one mutates in place and
    returns ``None``, one upscales when you meant "no bigger than", and the
    one called ``fit`` crops.

:mod:`mullion.background`
    Border-seeded background cleaning, so a near-white product shot sits flush
    on a white surface without a global threshold eating the subject's own
    highlights.

:mod:`mullion.watermark`
    A discreet text mark, sized against the shorter side with clamps at both
    ends, over a halo so it survives a bright sky.

And on the way out:

:mod:`mullion.encode`
    The pair to the open. A format that cannot carry an alpha channel gets the
    transparency composited rather than dropped — which is where the black
    rectangle comes back, in the shape of an innocent-looking repair for
    ``cannot write mode RGBA as JPEG``.

:mod:`mullion.page`
    Page geometry and DPI, so "A4 at 300" resolves to pixels that agree with
    the resolution written into the file.

Importing this package costs nothing: Pillow is imported inside the functions
that need it, so a service that only reaches for :mod:`mullion.page`, or that
imports at module scope and opens images rarely, does not pay for it at start-up.

Quick start::

    from mullion import contain, encode, open_bytes, watermark

    image = open_bytes(upload.read())              # RGB, upright, no black box
    avatar = open_path(p, keep_alpha=True)         # RGBA preserved

    hero = watermark(contain(image, (1280, 720)), "example.com")
    body = encode(hero, "JPEG", quality=88)        # flattened, not blackened
"""

from __future__ import annotations

from .background import (
    DEFAULT_BORDER_COVERAGE,
    DEFAULT_BORDER_TOLERANCE,
    DEFAULT_TOLERANCE,
    BackgroundCleanMode,
    CleanResult,
    clean_background,
    keeps_alpha,
    looks_like_white_background,
)
from .encode import encode, supports_alpha
from .page import (
    DEFAULT_DPI,
    MM_PER_INCH,
    NAMED_PAGE_SIZES_MM,
    PageGeometry,
    PageUnit,
    named_page_geometry,
    resolve_page_geometry,
    to_pixels,
    validate_dpi,
)
from .resize import Box, contain, cover
from .source import (
    WHITE,
    Matte,
    flatten_onto,
    has_transparency,
    normalize,
    open_bytes,
    open_path,
)
from .watermark import DEFAULT_WATERMARK_STYLE, Corner, WatermarkStyle, watermark

__version__ = "0.2.1"

__all__ = [
    "DEFAULT_BORDER_COVERAGE",
    "DEFAULT_BORDER_TOLERANCE",
    "DEFAULT_DPI",
    "DEFAULT_TOLERANCE",
    "DEFAULT_WATERMARK_STYLE",
    "MM_PER_INCH",
    "NAMED_PAGE_SIZES_MM",
    "WHITE",
    "BackgroundCleanMode",
    "Box",
    "CleanResult",
    "Corner",
    "Matte",
    "PageGeometry",
    "PageUnit",
    "WatermarkStyle",
    "__version__",
    "clean_background",
    "contain",
    "cover",
    "encode",
    "flatten_onto",
    "has_transparency",
    "keeps_alpha",
    "looks_like_white_background",
    "named_page_geometry",
    "normalize",
    "open_bytes",
    "open_path",
    "resolve_page_geometry",
    "supports_alpha",
    "to_pixels",
    "validate_dpi",
    "watermark",
]
