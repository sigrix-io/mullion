<p align="center">
  <img src="https://raw.githubusercontent.com/sigrix-io/mullion/main/.github/social-preview.png" alt="Mullion — one correct way to open an image" width="800">
</p>

# Mullion

**One correct way to open an image — and to write it back out.** EXIF
orientation applied, transparency resolved rather than dropped at both ends,
and a background cleaner that does not eat the subject.

A mullion is the upright that divides a window into panes — one stone member,
every pane set against it. That is the argument of this library: an application
that opens user images in six places gets six different answers, and the fix is
one member they all lean on.

```python
from mullion import contain, encode, open_bytes, watermark

image = open_bytes(upload.read())          # RGB, upright, no black rectangle
avatar = open_path(path, keep_alpha=True)  # RGBA preserved

hero = watermark(contain(image, (1280, 720)), "example.com")
body = encode(hero, "JPEG", quality=88)    # composited, not blackened
```

## The defect this exists for

`Image.open(...).convert("RGB")` is the spelling everyone reaches for, and it is
wrong in two ways that both render as a *plausible* picture rather than an error.

**Transparency composites against black.** `convert("RGB")` on an `RGBA` image
drops the alpha channel and keeps whatever RGB sits underneath. In a PNG written
by almost every tool, fully transparent pixels carry `(0, 0, 0)` — so a cutout
lands on a white page inside a black box.

```python
>>> from PIL import Image
>>> logo = Image.open("cutout.png")          # RGBA, transparent corners
>>> logo.convert("RGB").getpixel((0, 0))
(0, 0, 0)
>>> open_path("cutout.png").getpixel((0, 0))
(255, 255, 255)
```

The same is true of `LA` (greyscale + alpha) and of palette `P` images carrying
a `transparency` entry — which is what most "small" PNGs are saved as, and the
one that is easiest to miss, because the alpha is not in the mode string at all.
It is a key in `info`.

**EXIF orientation is ignored.** A photo shot in portrait on a phone is stored
landscape with a tag telling the viewer to rotate it. Pillow does not apply that
tag on open. Because placement is usually aspect-preserving, a wrongly-rotated
photo comes out *small and sideways* rather than obviously broken.

Neither is loud. The response is a 200, the picture renders, the layout is
right. A status-code test cannot see it and a reviewer looking at one image at a
time will not catch it.

This is measured, not hypothetical. Across one production codebase the same
transparent PNG came back on a black rectangle through three upload paths and
correctly through four others, because each had been written independently.

## Install

```bash
pip install mullion
```

Python 3.11+, and Pillow is the only dependency.

Importing the package costs nothing — Pillow is imported inside the functions
that need it, so a service that imports at module scope and opens images rarely
does not pay for it at start-up.

## What it does

### `mullion.source` — one correct open

```python
from mullion import normalize, open_bytes, open_path, has_transparency, flatten_onto

normalize(pil_image)                       # the core: any Image in, upright RGB out
normalize(pil_image, keep_alpha=True)      # RGBA out instead
normalize(pil_image, matte=(18, 18, 22))   # composite onto something other than white

open_bytes(data)                           # adapter: bytes from object storage or an upload
open_path("photo.jpg")                     # adapter: a filesystem path
```

`normalize` is the whole rule and the adapters are three lines each. That split
is deliberate: a path-only API is unusable from a web service holding bytes, and
a bytes-only API forces a batch tool to read every file into memory first.

`keep_alpha=False` composites transparency onto `matte` and returns `RGB` — what
an opaque destination wants. `keep_alpha=True` returns `RGBA`, for a caller that
will composite itself or write a cutout. Neither mutates the input.

**The adapters close the source before you see it.** Everything here returns a
new image, so nothing you could have read off the original survives on the
result — `n_frames` is `1` whatever the source held, and `format` is `None`.
With `normalize` that costs nothing, because you still hold the source and can
read it either side of the call. With `open_bytes` and `open_path` there is no
source to hold, so a caller that needs to *inspect* what arrived has to open it
itself:

```python
# Wrong, and quiet: every animation reports one frame, the re-encode
# succeeds, and only the motion is missing.
image = open_bytes(payload)
if getattr(image, "n_frames", 1) > 1:
    raise Refused("animated uploads are not accepted")

# Right: read the source while you still have it.
with Image.open(BytesIO(payload)) as source:
    if getattr(source, "n_frames", 1) > 1:
        raise Refused("animated uploads are not accepted")
    image = normalize(source)
```

The rule in one line: **want pixels, use an adapter; want to know what arrived,
use `normalize` and open it yourself.**

### `mullion.resize` — fit to a box, contain or cover

Pillow has three spellings for this and they do not agree. `thumbnail` mutates
in place and returns `None`, so `smaller = image.thumbnail(box)` binds nothing
and edits the image somebody else is holding. `resize` always scales, so a
caller who meant "no bigger than 800px" upscales a 200px upload and ships a
blurred picture. And `ImageOps.fit` is named fit and *crops*.

So these two are named for what they do to the content, in the vocabulary CSS
settled on:

```python
from mullion import contain, cover

thumb = contain(image, (400, 400))            # all of it, may leave space
card = cover(image, (1200, 630))              # fills exactly, may cut
face = cover(image, (400, 400), centering=(0.5, 0.0))   # keep the top
```

`contain` does not upscale unless you pass `upscale=True`, and both return a
new image. `contain` is built on `thumbnail`, so moving an existing
`image.thumbnail(box, LANCZOS)` call onto it gives the same pixels, not merely
a similar picture.

### `mullion.background` — clean a near-white background

A "white" background is rarely `#FFFFFF`. It is `#FBFBFA` from a scanner,
`#F7F8F9` from a phone's auto white balance, or a ring of `#FDFDFD` compression
noise around a cutout. Each reads as a faint rectangle around the image.

```python
from mullion import clean_background, keeps_alpha

mode = "flatten"                                    # or "transparent", or "off"
image = open_path(path, keep_alpha=keeps_alpha(mode))
cleaned, result = clean_background(image, mode=mode)

print(result.message)
# Cleaned background (63% of the image).
# ...or: No white background detected; image left unchanged.
```

Two rules make this safe to run over everything:

- **Only what touches the border is cleaned.** A global "brighter than
  *threshold* becomes white" pass is the obvious implementation and it eats the
  subject — the highlight on a white mug, the page of an open book, a bride's
  dress, the sky behind a building. This flood-fills *inward from the edges*, so
  a pixel is cleaned only when there is a continuous near-white path from it to
  the frame. Interior highlights are unreachable and survive.
- **Each image decides whether it has a background at all.** An image whose
  border is not near-white — a full-bleed photograph, a dark render — comes back
  untouched rather than partly eaten, and `result` says so. Ask
  `looks_like_white_background()` directly if you want the verdict without the
  work.

There is deliberately no `open_and_clean` convenience. It would have to restate
every keyword argument of both halves, and `keeps_alpha()` already names the one
coupling between them — opening without it flattens an existing cutout onto
white *before* cleaning, which leaves a pale fringe on the anti-aliased edges.

### `mullion.watermark` — a mark that survives a bright sky

```python
from mullion import watermark

marked = watermark(hero, "example.com")       # bottom-right, RGBA out
```

Sized against the image's **shorter** side with clamps at both ends, so it is
neither illegible on a thumbnail nor billboard-sized on a large render, and so
a portrait and a landscape version of the same picture get the same visual
weight. Drawn over a soft offset halo in the opposite ink — without it, white
type disappears into a bright sky and reads as a rendering fault.

Everything about the look is a `WatermarkStyle`, which is frozen and has the
measured defaults; pass your own for a different corner, ink or scale, or pass
`font=` to bring your own face. Empty text returns the image unchanged, because
"do not mark" is a legitimate thing for a caller's configuration to say.

It takes and returns an image rather than bytes on purpose: the mark belongs
*between* the resize and the encode. Marking first resamples the type along
with the picture and softens it; marking after the encode means decoding the
output again.

### `mullion.encode` — the black rectangle, on the way out

An `RGBA` image handed to a JPEG encoder raises `cannot write mode RGBA as
JPEG`, which is loud and therefore fine — except for what it provokes. The
obvious repair reads like a type fix and is the defect this library exists for,
reintroduced at the other end of the pipeline:

```python
image.convert("RGB").save(buffer, format="JPEG")   # black rectangle, again
```

`encode` is the pair to `open_bytes`. The caller says what they are writing,
not what mode the image needs to be in:

```python
from mullion import encode, supports_alpha

body = encode(image, "JPEG", quality=88, optimize=True)  # composited, not blackened
body = encode(image, "WEBP", quality=82, method=6)       # alpha kept
body = encode(page_image, "PNG", dpi=(page.dpi, page.dpi))

supports_alpha("PNG")     # True
supports_alpha("JPEG")    # False
```

Which formats can carry alpha is asked of Pillow — by writing one transparent
pixel and seeing whether the encoder objects — rather than answered from a
table kept here, because the table would be wrong in both directions: AVIF
depends on a plugin that may not be installed, and a format added in a later
Pillow would go unrecognised by a library that thinks it knows them all.

> "Can carry an alpha channel" is not "carries yours faithfully". GIF answers
> `True` and has exactly one bit of it, so a soft edge is snapped rather than
> composited. If that matters, flatten deliberately with `flatten_onto`.

### `mullion.page` — page geometry and DPI

3000 px is 10 inches at 300 DPI and 41.7 inches at 72. Nothing in a file says
which unless something writes the resolution into it.

```python
from mullion import named_page_geometry, resolve_page_geometry

page = named_page_geometry("a4", dpi=300)
page.description          # '2480x3508px (8.27x11.69in at 300 DPI)'

page = resolve_page_geometry(page_width=8, page_height=10, unit="in", dpi=300)
canvas = Image.new("RGB", (page.width_px, page.height_px), "white")
canvas.save("out.png", dpi=(page.dpi, page.dpi))
```

The pixels and the DPI travel together, so the two cannot disagree. `a4`, `a3`,
`a5`, `letter`, `legal` and `tabloid` are named; anything else is `px`, `in` or
`mm`. This module imports nothing at all — it is arithmetic with the constants
written down.

> A PNG stores resolution in its `pHYs` chunk as pixels *per metre*, as an
> integer. 300 DPI is 11811.02… px/m, so it is stored as 11811 and reads back as
> 299.9994. That is the format, not a defect — compare with a tolerance.

## What it is not

Not a general imaging toolkit. Pillow already is one, and this library is a thin
correctness layer over it, not a wrapper around it — you get a real
`PIL.Image.Image` back and do whatever you like with it.

Specifically out of scope: colour management, subject-aware or model-based
background removal, and laying multiple images out on a page. That last one is
where the line falls: **this library handles one image; composing several is
the application's job.**

Two things that used to be on that list are now in the library, and the reason
is worth stating rather than quietly editing out. Resizing was excluded because
"`ImageOps.fit` and friends already do this well" — which was the same mistake
this library exists to correct, one level up: there are three spellings, they
disagree, and the disagreement is quiet. And encoding was excluded as "format
conversion", which it is not: choosing what happens to an alpha channel the
target format cannot hold is the *same* transparency decision `open_bytes`
makes, arriving at the other end of the pipeline. Both were drawn the way a
scope line usually is, from the shape of the code rather than from where the
defects were.

## Versioning

Pre-1.0. Nothing is stable, and any `0.x` release may break any other — see
[VERSIONING.md](https://github.com/sigrix-io/mullion/blob/main/VERSIONING.md), which is blunt about what that means. If you are
building on `0.x`, please [open an issue](https://github.com/sigrix-io/mullion/issues) saying so; the practical
difference between an announced breaking change and a surprising one is knowing
somebody is out there.

## Contributing

[CONTRIBUTING.md](https://github.com/sigrix-io/mullion/blob/main/CONTRIBUTING.md) is candid about what a small team can promise.
Security findings go to **security@sigrix.io** and never to a public issue —
[SECURITY.md](https://github.com/sigrix-io/mullion/blob/main/SECURITY.md).

## Licence

[Apache-2.0](https://github.com/sigrix-io/mullion/blob/main/LICENSE).
