"""Mullion — get an image in correctly, once.

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

So this library is deliberately small, and does the three things that keep
coming back:

:mod:`mullion.source`
    One correct open — EXIF orientation applied, transparency resolved rather
    than dropped — with adapters for the two things callers actually hold:
    ``bytes`` from object storage and a filesystem path.

:mod:`mullion.background`
    Border-seeded background cleaning, so a near-white product shot sits flush
    on a white surface without a global threshold eating the subject's own
    highlights.

:mod:`mullion.page`
    Page geometry and DPI, so "A4 at 300" resolves to pixels that agree with
    the resolution written into the file.

Importing this package costs nothing: Pillow is imported inside the functions
that need it, so a service that only reaches for :mod:`mullion.page`, or that
imports at module scope and opens images rarely, does not pay for it at start-up.

Quick start::

    from mullion import open_bytes, open_path, clean_background, keeps_alpha

    image = open_bytes(upload.read())              # RGB, upright, no black box
    avatar = open_path(p, keep_alpha=True)         # RGBA preserved

    mode = "flatten"
    shot = open_path(p, keep_alpha=keeps_alpha(mode))
    cleaned, result = clean_background(shot, mode=mode)
    print(result.message)
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
from .source import (
    WHITE,
    Matte,
    flatten_onto,
    has_transparency,
    normalize,
    open_bytes,
    open_path,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_BORDER_COVERAGE",
    "DEFAULT_BORDER_TOLERANCE",
    "DEFAULT_DPI",
    "DEFAULT_TOLERANCE",
    "MM_PER_INCH",
    "NAMED_PAGE_SIZES_MM",
    "WHITE",
    "BackgroundCleanMode",
    "CleanResult",
    "Matte",
    "PageGeometry",
    "PageUnit",
    "__version__",
    "clean_background",
    "flatten_onto",
    "has_transparency",
    "keeps_alpha",
    "looks_like_white_background",
    "named_page_geometry",
    "normalize",
    "open_bytes",
    "open_path",
    "resolve_page_geometry",
    "to_pixels",
    "validate_dpi",
]
