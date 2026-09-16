"""Fit an image to a box, without the three ways that usually goes wrong.

Resizing is the one operation in this library that nobody gets *silently*
wrong in the way :mod:`mullion.source` exists for — a mis-sized picture is
visible. What is not visible is which of Pillow's several spellings a caller
reached for, and they do not mean the same thing:

``thumbnail`` **mutates in place and returns ``None``.** ``smaller =
image.thumbnail(box)`` binds ``None``, and the original is modified underneath
whoever else is holding it. It is the only resize in Pillow that works this
way, and it is the one whose name reads like a conversion.

``resize`` **always scales, in both directions.** A caller who means "no
bigger than 800px" and reaches for ``resize`` upscales a 200px upload to 800
and ships a blurred picture. ``thumbnail`` declines to upscale; ``resize``
has no opinion.

``ImageOps.fit`` **crops.** Its name says fit and it covers the box, cutting
whatever does not fit — which is right for a card and wrong for a product
shot whose edges are the point.

So the two operations are named here for what they do to the *content*, in
the vocabulary CSS settled on: :func:`contain` keeps all of it and may leave
space, :func:`cover` fills the box and may cut. Both return a new image and
leave the input alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL.Image import Image as PILImage
    from PIL.Image import Resampling

__all__ = ["Box", "contain", "cover"]

#: A target size in pixels, ``(width, height)``.
Box = tuple[int, int]


def _resample(resample: Resampling | None) -> Resampling:
    """Lanczos unless the caller said otherwise.

    Resolved here rather than as a default argument so that importing this
    module does not import Pillow — the enum member is only reachable through
    ``PIL.Image``, and evaluating it in a signature would pull the whole
    dependency in at import time for every caller, including the ones that
    never resize anything.
    """
    from PIL import Image

    return Image.Resampling.LANCZOS if resample is None else resample


def _check(box: Box) -> Box:
    width, height = box
    if width <= 0 or height <= 0:
        raise ValueError(f"Box dimensions must be greater than zero, got {box!r}.")
    return int(width), int(height)


def contain(
    image: PILImage | Any,
    box: Box,
    *,
    upscale: bool = False,
    resample: Resampling | None = None,
) -> PILImage:
    """Return a copy of ``image`` scaled to fit inside ``box``, aspect kept.

    Nothing is cropped, so the result is no larger than ``box`` in either
    dimension and usually smaller in one of them. With ``upscale=False`` — the
    default, and what ``thumbnail`` does — an image already inside the box is
    returned at its own size rather than blown up to fill it.

    This is a copy. ``thumbnail`` is the in-place spelling and the source of
    the ``None`` above; the price of returning a new image is one copy, which
    is what makes the call safe to write in an expression.
    """
    target = _check(box)
    working = image.copy()

    if not upscale:
        # Deliberately ``thumbnail`` rather than arithmetic and ``resize``:
        # it carries Pillow's own reducing-gap pre-pass, so a caller moving
        # from ``image.thumbnail(box, LANCZOS)`` to this gets the same pixels
        # out, not merely a similar picture.
        working.thumbnail(target, _resample(resample))
        return working

    width, height = working.size
    scale = min(target[0] / width, target[1] / height)
    scaled = (max(1, round(width * scale)), max(1, round(height * scale)))
    return working.resize(scaled, _resample(resample))


def cover(
    image: PILImage | Any,
    box: Box,
    *,
    centering: tuple[float, float] = (0.5, 0.5),
    resample: Resampling | None = None,
) -> PILImage:
    """Return a copy of ``image`` filling ``box`` exactly, cropping the excess.

    The result is always ``box``, which is what a fixed-size card, grid cell or
    social preview needs. ``centering`` says which part survives the crop:
    ``(0.5, 0.5)`` keeps the middle, ``(0.5, 0.0)`` keeps the top, which is
    usually where a face is.

    Unlike :func:`contain` this *will* upscale, because it has no choice: the
    box is filled by definition.
    """
    from PIL import ImageOps

    return ImageOps.fit(image, _check(box), method=_resample(resample), centering=centering)
