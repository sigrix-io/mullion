# Mullion

**One correct way to open an image.** EXIF orientation applied, transparency
resolved rather than dropped, and a background cleaner that does not eat the
subject.

A mullion is the upright that divides a window into panes — one stone member,
every pane set against it. That is the argument of this library: an application
that opens user images in six places gets six different answers, and the fix is
one member they all lean on.

```python
from mullion import open_bytes, open_path

image = open_bytes(upload.read())        # RGB, upright, no black rectangle
avatar = open_path(path, keep_alpha=True)  # RGBA preserved
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

Specifically out of scope: resizing and cropping (`ImageOps.fit` and friends
already do this well), format conversion, colour management, subject-aware or
model-based background removal, and laying multiple images out on a page. That
last one is where the line falls: **this library handles one image; composing
several is the application's job.**

## Versioning

Pre-1.0. Nothing is stable, and any `0.x` release may break any other — see
[VERSIONING.md](VERSIONING.md), which is blunt about what that means. If you are
building on `0.x`, please [open an issue](../../issues) saying so; the practical
difference between an announced breaking change and a surprising one is knowing
somebody is out there.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) is candid about what a small team can promise.
Security findings go to **security@sigrix.io** and never to a public issue —
[SECURITY.md](SECURITY.md).

## Licence

[Apache-2.0](LICENSE).
