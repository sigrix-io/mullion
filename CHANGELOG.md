# Changelog

All notable changes are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [VERSIONING.md](VERSIONING.md) — read it before pinning, because
pre-1.0 means what it says.

## [Unreleased]

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
