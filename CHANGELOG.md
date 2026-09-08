# Changelog

All notable changes are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [VERSIONING.md](VERSIONING.md) — read it before pinning, because
pre-1.0 means what it says.

## [Unreleased]

### Fixed

- The annotations `py.typed` promises are now verified. The wheel ships
  `src/mullion/py.typed` and the package declares `Typing :: Typed`, which
  together tell a consumer's type checker to trust these annotations — but
  nothing had ever run one, and `mypy --strict` reported nine errors on the
  first release. All nine were `Image.load()`, typed `PixelAccess | None` and
  indexed without narrowing. Nothing raised: a wrong annotation just makes
  somebody else's type checker confidently green about the wrong thing.
  ([#3](https://github.com/sigrix-io/mullion/issues/3))

### Changed

- `mullion.background`'s two internal pixel readers now assert the image mode
  they were written for instead of assuming it, so a caller handing one the
  wrong mode fails immediately rather than reading a shape nothing checks.
  No public API changed.

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
