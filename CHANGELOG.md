# Changelog

All notable changes are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [VERSIONING.md](VERSIONING.md) — read it before pinning, because
pre-1.0 means what it says.

## [Unreleased]

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
