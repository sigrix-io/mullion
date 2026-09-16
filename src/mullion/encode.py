"""Get the image back out again, for a format that may not carry what it holds.

:mod:`mullion.source` is about the way in, where dropping an alpha channel
leaves a black rectangle. This module is the way out, where the *same* defect
is waiting behind a different door.

An ``RGBA`` image handed to a JPEG encoder raises::

    OSError: cannot write mode RGBA as JPEG

which is loud, and therefore fine — except for what it provokes. The obvious
repair is the one that reads like a type fix:

.. code-block:: python

    image.convert("RGB").save(buffer, format="JPEG")   # black rectangle, again

That is the identical bug, reintroduced by a change whose whole purpose was to
make an error go away, in a codebase that may already have fixed it on the way
in. The encoder is satisfied, the bytes are a valid JPEG, and the cutout is on
black.

:func:`encode` is the pair to ``open_bytes``: it composites onto a matte when
the target format cannot carry transparency, and leaves the channel alone when
it can. The caller says what they are writing, not what mode the image needs
to be in.

Which formats those are is asked of Pillow rather than answered from a list
kept here, because the list would be wrong in both directions — AVIF support
depends on a plugin that may not be installed, and a format added in a later
Pillow would go unrecognised by a library that thinks it knows them all.
"""

from __future__ import annotations

from functools import cache
from io import BytesIO
from typing import TYPE_CHECKING, Any

from .source import WHITE, Matte, flatten_onto

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL.Image import Image as PILImage

__all__ = ["encode", "supports_alpha"]


@cache
def supports_alpha(image_format: str) -> bool:
    """Whether Pillow, *as installed here*, can write alpha in this format.

    Answered by writing a one-pixel transparent image and seeing whether the
    encoder objects. That costs one trivial save per format per process, and
    it is the only answer that stays true: whether AVIF can be written at all
    depends on a plugin, and a table in this file would go stale the release
    after it was written.

    "Can carry an alpha channel" is not "carries yours faithfully". GIF
    answers ``True`` and has exactly one bit of it, so a soft edge is snapped
    to on-or-off rather than composited. If that distinction matters, flatten
    deliberately with :func:`mullion.flatten_onto` instead of leaving it to
    the encoder.

    An unknown or unwritable format answers ``False``, so :func:`encode`
    flattens and then lets Pillow raise its own error about the format — the
    complaint names the real problem rather than the mode.
    """
    from PIL import Image

    probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    try:
        probe.save(BytesIO(), format=image_format.upper())
    except Exception:
        return False
    return True


def encode(
    image: PILImage | Any,
    image_format: str,
    *,
    matte: Matte = WHITE,
    **options: Any,
) -> bytes:
    """Encode ``image`` to ``image_format``, resolving what the format cannot hold.

    Transparency is composited onto ``matte`` when the target cannot carry it,
    and left untouched when it can. ``options`` go straight to Pillow's
    ``save``, so quality, compression and metadata are the caller's::

        encode(shot, "WEBP", quality=82, method=6)
        encode(shot, "JPEG", quality=88, optimize=True, progressive=True)
        encode(page, "PNG", dpi=(geometry.dpi, geometry.dpi))

    That last one is the seam with :mod:`mullion.page`: pass the DPI the
    geometry was resolved at and the file says what size it is meant to be.

    The input is never mutated — flattening builds a new image, and an image
    that needs no flattening is saved as it stands.
    """
    buffer = BytesIO()
    working = image if supports_alpha(image_format) else flatten_onto(image, matte)
    working.save(buffer, format=image_format.upper(), **options)
    return buffer.getvalue()
