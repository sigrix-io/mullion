# Changelog

All notable changes are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [VERSIONING.md](VERSIONING.md) — read it before pinning, because
pre-1.0 means what it says.

## [Unreleased]

## [0.2.0]

The library reached the other end of the pipeline. Everything it did before was
about getting an image *in*; a consumer adopting `open_bytes` found that the
same defect was waiting on the way out, in code that was never making a
transparency decision at all.

### Added

- `mullion.encode` — `encode()` and `supports_alpha()`. An `RGBA` image handed
  to a JPEG encoder raises `cannot write mode RGBA as JPEG`, which is loud and
  therefore harmless in itself. What it provokes is not: the obvious repair is
  `image.convert("RGB")`, which reads like a type fix and is precisely the
  black-rectangle defect this library exists for, reintroduced at the far end
  of a pipeline that may already have fixed it at the near end. `encode()`
  composites onto a matte when the target format cannot carry transparency and
  leaves the channel alone when it can, so the caller says what they are
  writing rather than what mode the image must be in.

  Which formats those are is asked of Pillow, by writing one transparent pixel
  and seeing whether the encoder objects, rather than answered from a table
  kept here. A table would be wrong in both directions: AVIF depends on a
  plugin that may not be installed, and a format added in a later Pillow would
  go unrecognised by a library that believes it knows them all. Note that "can
  carry alpha" is not "carries yours faithfully" — GIF answers yes with one bit
  of it.

- `mullion.resize` — `contain()` and `cover()`. Pillow has three spellings for
  fitting an image to a box and they disagree in ways that are quiet rather
  than loud: `thumbnail` mutates in place and returns `None`, so
  `smaller = image.thumbnail(box)` binds nothing and edits an image somebody
  else is holding; `resize` scales in both directions, so "no bigger than
  800px" blurs a 200px upload up to 800; and `ImageOps.fit` is named fit and
  crops. These two are named for what they do to the content, in the vocabulary
  CSS settled on. `contain()` is built on `thumbnail`, deliberately — it
  carries Pillow's own reducing-gap pre-pass, so moving an existing
  `image.thumbnail(box, LANCZOS)` call onto it produces the same pixels rather
  than a similar picture.

- `mullion.watermark` — `watermark()`, with `WatermarkStyle` and
  `DEFAULT_WATERMARK_STYLE`. A text mark sized against the image's shorter side
  with clamps at both ends, over an offset halo. Each of those is a failure
  somebody else's photograph produces: a fixed size is illegible on a thumbnail
  and billboard-sized on a large render, scaling off the width alone re-weights
  every portrait image, and white type without a halo vanishes into a bright
  sky and reads as a rendering fault. The style is frozen and every knob is in
  it; the policy question — whether a font fault should fail the request or
  ship the picture unmarked — is deliberately left to the caller, and is
  usually the second.

### Changed

- The README's scope list no longer excludes resizing and encoding, and says
  why rather than quietly dropping them. Resizing was excluded because
  "`ImageOps.fit` and friends already do this well", which was this library's
  own mistake one level up — there are three spellings, they disagree, and the
  disagreement is quiet. Encoding was excluded as "format conversion", which it
  is not: deciding what happens to an alpha channel the target cannot hold is
  the same transparency decision `open_bytes` makes, at the other end. Both
  lines were drawn from the shape of the code rather than from where the
  defects were.

- `open_bytes()` and `open_path()` document what they close over. Both open the
  source inside the call and return a converted copy, so nothing only the source
  could answer survives on the result — `n_frames` reads `1` for an animation
  and `format` reads `None`. No behaviour changed; this was true since the
  adapters were written and nothing said so, which matters because the way it
  goes wrong is the kind this library exists to remove: a caller refusing
  animated uploads is told `1`, stores one frame, and nothing raises. The rule
  is now in both docstrings, in `normalize()`'s, and in the README — want
  pixels, use an adapter; want to know what arrived, use `normalize()` and open
  the source yourself. Pinned by tests, with a canary so a still fixture cannot
  make them pass vacuously.
  ([#18](https://github.com/sigrix-io/mullion/issues/18))

## [0.1.1]

### Fixed

- `clean_background()` no longer costs a second per megapixel. Above a longest
  edge of 1024px the flood runs on a reduced copy, which took a 24MP
  photograph from 38.8s to 2.7s and a 12MP one from 18.2s to 1.9s on the same
  machine; below that nothing changed. `ImageDraw.floodfill` is pure Python and
  was the whole cost — profiling a 12MP call put a single flood at 18.7s of it,
  with every vectorised step around it under a tenth of a second. A caller
  composing a page from a folder of phone-sized photographs was spending
  minutes inside a request.

  Only the *connectivity* answer comes from the reduced copy; membership stays
  full resolution, because the reached region is intersected back with the
  full-resolution candidates. That ordering is what keeps a pixel that is not
  near-white from ever being cleaned, however coarse the small copy is.

  What it costs, measured rather than reasoned about: a wall separating an
  enclosed near-white region from the background survives while it is roughly
  1.5x the scale factor or thicker. The factor tracks the image, so that limit
  is scale-invariant — about 0.15% of the longest edge at any size, or 9px on a
  24MP photo. A gap thinner than that closes and the region behind it is
  cleaned as background.
  ([#9](https://github.com/sigrix-io/mullion/issues/9))

- The README's links and its cover image are absolute URLs. `pyproject.toml`
  sets `readme = "README.md"`, so that file is the long description PyPI
  renders — and PyPI resolves a relative path against `pypi.org`, not against
  the repository. Every one of them 404'd on the package page: the cover
  image, and the links to `VERSIONING.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `LICENSE` and the issue tracker. The first of those matters most, since the
  README asks a reader to open `VERSIONING.md` before pinning and pre-1.0 is
  when that advice counts. `twine check` passes either way — it checks that
  the markup renders, not that what it points at exists — so a test now does.

## [0.1.0]

First release.

### Added

- `mullion.source` — `normalize()`, and the `open_bytes()` / `open_path()`
  adapters over it. Applies the EXIF orientation tag and resolves transparency
  in all three shapes it arrives in: `RGBA`, `LA`, and palette `P` carrying a
  `transparency` key in `info`. `keep_alpha` chooses between compositing onto a
  matte and preserving the channel.
- `mullion.background` — `clean_background()`, border-seeded so that a
  near-white region enclosed by the subject is never mistaken for the
  background around it. `looks_like_white_background()` answers the same
  verdict without doing the work, and `keeps_alpha()` names the one coupling
  between the open call and the clean call.
- `mullion.page` — `resolve_page_geometry()` and `named_page_geometry()`,
  returning pixels and the DPI they were derived at as one value.

### Changed

- `mullion.background`'s two internal pixel readers assert the image mode they
  were written for instead of assuming it, so a caller handing one the wrong
  mode fails immediately rather than reading a shape nothing checks. No public
  API changed.

### Fixed

- The annotations `py.typed` promises are verified. The wheel ships
  `src/mullion/py.typed` and the package declares `Typing :: Typed`, which
  together tell a consumer's type checker to trust these annotations — but
  nothing had ever run one, and `mypy --strict` reported nine errors. All nine
  were `Image.load()`, typed `PixelAccess | None` and indexed without
  narrowing. Nothing raised: a wrong annotation just makes somebody else's type
  checker confidently green about the wrong thing.
  ([#3](https://github.com/sigrix-io/mullion/issues/3))
