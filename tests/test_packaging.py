"""What the package page says, which is not what the repository page says.

``pyproject.toml`` sets ``readme = "README.md"``, so that file is the long
description PyPI renders. The two hosts resolve a relative path differently:
GitHub resolves it against the repository, PyPI against ``pypi.org``, where
none of these files are. So a link that is correct in every review and every
local preview arrives on the package page as a 404, and stays there for the
life of the release — a published version's metadata is immutable.

This is not hypothetical and it is not caught by the obvious check. `0.1.0`
shipped with five relative links, and `0.1.1` nearly shipped with a relative
cover image on top of them. ``twine check`` **passed** on that wheel: it
validates that the description renders, not that the things it points at
exist.

The link to ``VERSIONING.md`` is the one that makes this worth a test rather
than a habit. The README asks a reader to open it before pinning, and pre-1.0
is exactly when that advice matters — so the reader most likely to need it is
the one arriving from PyPI, and they are the one who cannot follow it.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: An href or src that PyPI can resolve. Anchors stay in the document, so they
#: are fine; a bare scheme-relative ``//host/path`` is not, since the package
#: page is served over https and the intent is never clear.
_RESOLVES_ANYWHERE = re.compile(r"^(https?://|mailto:|#)")

_HTML_SRC = re.compile(r"<img[^>]*\ssrc=\"([^\"]+)\"", re.I)
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
_MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)")


def _readme_named_by_pyproject() -> Path:
    """The file that actually becomes the long description.

    Read out of ``pyproject.toml`` rather than hardcoded, so that pointing
    ``readme`` at a different file moves this guard with it instead of
    silently leaving it testing a file nobody publishes.
    """
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    named = config["project"]["readme"]
    # The key also accepts a table; only the string form is in use here, and a
    # switch to the table form should fail loudly rather than be guessed at.
    assert isinstance(named, str), f"readme is {named!r}; teach this guard the table form"
    return ROOT / named


def _references(text: str) -> list[tuple[str, str]]:
    """Every outbound reference in ``text``, as (kind, target)."""
    found = [("img", m.group(1)) for m in _HTML_SRC.finditer(text)]
    found += [("image", m.group(1)) for m in _MD_IMAGE.finditer(text)]
    found += [("link", m.group(1)) for m in _MD_LINK.finditer(text)]
    return found


def test_every_readme_reference_resolves_off_github() -> None:
    readme = _readme_named_by_pyproject()
    references = _references(readme.read_text())

    # A sweep that finds nothing and a README with nothing to find read
    # identically. This README has both images and links today; if a rewrite
    # leaves it with neither, that is worth noticing rather than passing.
    assert references, f"{readme.name} has no links or images — did the patterns go stale?"

    relative = [
        f"{kind} -> {target}" for kind, target in references if not _RESOLVES_ANYWHERE.match(target)
    ]
    assert relative == [], (
        f"{readme.name} is the PyPI long description, and PyPI resolves these "
        f"against pypi.org rather than the repository, so each is a 404 on the "
        f"package page: {relative}"
    )


def test_the_readme_pyproject_names_is_the_one_that_exists() -> None:
    """Guards the guard: a renamed README would make the sweep above vacuous."""
    assert _readme_named_by_pyproject().is_file()


@pytest.mark.parametrize("kind, target", [("img", ".github/x.png"), ("link", "VERSIONING.md")])
def test_the_sweep_rejects_a_relative_reference(kind: str, target: str) -> None:
    """The patterns match what they claim to, rather than never matching.

    Without this, a regex that silently stopped matching anything would leave
    the guard above green against a README of nothing but broken links.
    """
    markup = f'<img src="{target}">' if kind == "img" else f"[docs]({target})"
    assert _references(markup), f"the {kind} pattern no longer matches its own spelling"
    assert not _RESOLVES_ANYWHERE.match(target)
