"""One correct way to open an image, whatever you are holding.

Every consumer of a user-supplied image opens it, and the obvious spelling —
``Image.open(...).convert("RGB")`` — is wrong in two ways that both render as a
*plausible* picture rather than an error. That is why neither is noticed by a
status-code test, a screenshot review, or a human looking at one image at a
time.

**Transparency composites against black.** ``convert("RGB")`` on an ``RGBA``
image drops the alpha channel and keeps whatever RGB sits underneath it. In a
PNG written by almost every tool, fully transparent pixels carry ``(0, 0, 0)``
— so a cutout PNG lands on a white page inside a black rectangle. The same is
true of ``LA`` (greyscale + alpha), and of palette ``P`` images carrying a
``transparency`` entry, which is what most "small" PNGs are saved as. That last
one is the one that is easy to miss: the alpha is not in the mode string, it is
a key in ``info``.

**EXIF orientation is ignored.** A photo shot in portrait on a phone is stored
landscape with an orientation tag telling the viewer to rotate it. Pillow does
not apply that tag on open, so the image is placed rotated — and because most
placement is aspect-preserving, a wrongly-rotated image is merely *small and
sideways* rather than obviously broken.

:func:`normalize` fixes both, once. The two adapters exist because callers hold
different things: a web service holds ``bytes`` it just read from object
storage, and a desktop or batch tool holds a filesystem path. Neither should
have to reach for ``PIL`` to get an image in correctly.
"""

from __future__ import annotations

import os
from io import BytesIO
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL.Image import Image as PILImage

__all__ = [
    "WHITE",
    "Matte",
    "flatten_onto",
    "has_transparency",
    "normalize",
    "open_bytes",
    "open_path",
]

# Modes that carry per-pixel transparency. ``P`` is deliberately absent: it
# carries transparency out of band, in ``info["transparency"]``, and is handled
# separately in :func:`has_transparency`.
_ALPHA_MODES = frozenset({"RGBA", "LA", "PA"})

#: An RGB triple to composite transparency onto.
Matte = tuple[int, int, int]

#: The default matte. White, because the surfaces that flatten are pages and
#: cards, which are white.
WHITE: Matte = (255, 255, 255)


def has_transparency(image: PILImage | Any) -> bool:
    """Whether ``image`` carries transparency in any of its three shapes.

    Reads attributes rather than importing Pillow, so this stays usable against
    a stand-in in a test that does not want the dependency.
    """
    mode = getattr(image, "mode", "")
    if mode in _ALPHA_MODES:
        return True
    return mode == "P" and "transparency" in getattr(image, "info", {})


def flatten_onto(image: PILImage | Any, matte: Matte = WHITE) -> PILImage:
    """Composite ``image`` onto a solid ``matte``, returning ``RGB``.

    An image with no transparency is simply converted, so this is safe to call
    unconditionally.
    """
    from PIL import Image

    if not has_transparency(image):
        return image.convert("RGB")

    # Normalize every transparent shape to RGBA first. Converting a P-mode
    # image straight to RGB would discard info["transparency"] silently; going
    # via RGBA is what promotes it to a real alpha channel.
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (*matte, 255))
    return Image.alpha_composite(background, rgba).convert("RGB")


def normalize(
    image: PILImage | Any,
    *,
    keep_alpha: bool = False,
    matte: Matte = WHITE,
) -> PILImage:
    """Return ``image`` upright, with its transparency resolved.

    ``keep_alpha=False`` composites transparency onto ``matte`` and returns
    ``RGB`` — what an opaque destination wants, since it has no use for an
    alpha channel and dropping one carelessly is the black-rectangle defect
    this module exists for. ``keep_alpha=True`` returns ``RGBA`` instead, for a
    caller that will composite itself or write a cutout.

    Always returns a new image; the input is never mutated.

    Because it is a new image, nothing you could have read off the source
    survives on the result — ``n_frames`` is ``1`` whatever the source held,
    and ``format`` is ``None``. That is only a trap for the adapters below,
    which close the source before you see it; a caller of ``normalize`` still
    holds the original and can read from it either side of this call::

        with Image.open(BytesIO(payload)) as source:
            animated = getattr(source, "n_frames", 1) > 1
            image = normalize(source, keep_alpha=True)
    """
    from PIL import ImageOps

    # exif_transpose returns a new image with the tag applied and removed, and
    # is a no-op for a file with no orientation tag. Older Pillow returns None
    # rather than a copy in that case, hence the fallback.
    upright = ImageOps.exif_transpose(image) or image

    if not has_transparency(upright):
        # Convert unconditionally rather than returning ``upright`` as-is: the
        # adapters below open inside a ``with`` block, so a lazily-loaded image
        # would be read from a file that has since closed. ``convert`` forces
        # the load, which is what makes the return value safe to outlive it.
        return upright.convert("RGBA") if keep_alpha else upright.convert("RGB")

    if keep_alpha:
        return upright.convert("RGBA")
    return flatten_onto(upright, matte)


def open_bytes(
    data: bytes | bytearray | memoryview,
    *,
    keep_alpha: bool = False,
    matte: Matte = WHITE,
) -> PILImage:
    """Open image ``data`` held in memory, normalized.

    The adapter a web service wants: an upload or an object-storage read hands
    you bytes, and there is no file to point Pillow at.

    Raises whatever ``Image.open`` raises for data that is not an image —
    callers that treat an unreadable upload as a refusal already handle it.

    **Opens and closes the source inside this call**, so anything only the
    source could answer is gone by the time you get the result: ``n_frames``
    reads ``1`` for an animation, and ``format`` reads ``None``. A caller that
    refuses animated uploads, or branches on the incoming format, wants
    :func:`normalize` and its own ``Image.open`` instead. Getting this wrong is
    quiet rather than loud — a re-encode of the one frame succeeds and the
    bytes are a valid image.
    """
    from PIL import Image

    with Image.open(BytesIO(bytes(data))) as source:
        return normalize(source, keep_alpha=keep_alpha, matte=matte)


def open_path(
    path: str | os.PathLike[str],
    *,
    keep_alpha: bool = False,
    matte: Matte = WHITE,
) -> PILImage:
    """Open the image at ``path``, normalized.

    The adapter a batch or desktop tool wants. The file handle is closed before
    this returns; see :func:`normalize` for why that is safe, and for what it
    costs — as with :func:`open_bytes`, a caller that needs ``n_frames``,
    ``format`` or anything else off the source must open it itself.
    """
    from PIL import Image

    with Image.open(path) as source:
        return normalize(source, keep_alpha=keep_alpha, matte=matte)
