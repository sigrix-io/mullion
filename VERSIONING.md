# Versioning and compatibility

Mullion follows [Semantic Versioning](https://semver.org/), with the
pre-1.0 carve-out below.

## Before 1.0

**Nothing is stable. Any `0.x` release may break any other `0.x` release.**

This is stated plainly because the alternative — implying stability we cannot
yet promise — is how a library acquires dependents it then has to betray.
Mullion is published early on purpose: feedback is cheapest while changing
things is still free, and that is only true if everyone knows it is still true.

Concretely, before 1.0:

- Functions may be renamed, resignatured, or removed.
- Default values may move. The defaults in
  [`background.py`](src/mullion/background.py) — the tolerances and the
  coverage fraction — are tuned against a finite set of real images and will
  move as that set grows. A default moving changes *output*, not signatures, so
  it will not raise; the changelog is where it will be visible.
- Every breaking change is listed in [CHANGELOG.md](CHANGELOG.md) with a
  migration note.

**Pin the minor.** `mullion~=0.1.0` while we are pre-1.0.

If you are building on `0.x`, please [open an issue](../../issues) saying so.
The practical difference between an announced breaking change and a surprising
one is knowing somebody is out there.

## What a version bump will mean after 1.0

| Bump | Means |
|---|---|
| **Major** | A signature changed, a name was removed, or a default's *documented* behaviour changed. |
| **Minor** | Something was added. Existing calls keep working and keep answering the same. |
| **Patch** | A defect was fixed. Note that a fix to an image-processing defect necessarily changes output for the inputs that hit it — that is what a fix is. |

That last row is the one worth reading twice. In a library that produces
pixels, "no behaviour change" is not available: correcting a wrong answer
changes the answer. What a patch release promises is that the *previous* output
was wrong and the changelog says for which inputs.

## What is public

Everything exported from the top-level `mullion` package, which is exactly
what `mullion.__all__` lists. The submodules are importable and their
contents are documented, but a name that is not in `__all__` — anything with a
leading underscore especially — may move without a major version.

## The Pillow floor

`pyproject.toml` pins a floor rather than a ceiling. Raising the floor is a
**minor** bump, not a patch: a library that demands a newer Pillow than the
application already has is one the application cannot take, and that is a
compatibility break in every sense that matters to whoever is holding the
requirements file.
