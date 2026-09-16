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

import ast
import doctest
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


# --------------------------------------------------------------------------
# The examples on that page have to run
# --------------------------------------------------------------------------

_PY_BLOCK = re.compile(r"```python\n(.*?)```", re.S)


def _python_blocks(text: str) -> list[str]:
    """Every fenced python example, as source that can be parsed.

    Two shapes appear on this page and only one is runnable as written: plain
    source, and a ``>>>`` transcript showing a value coming back (which is how
    the black-rectangle demonstration is written, because the point is the
    tuple it prints). ``doctest`` already knows how to pull the statements out
    of the second, so the guard reads both rather than only the shape it
    happened to meet first.
    """
    blocks = []
    for block in _PY_BLOCK.findall(text):
        if ">>>" in block:
            blocks.append("\n".join(e.source for e in doctest.DocTestParser().get_examples(block)))
        else:
            blocks.append(block)
    return blocks


def _exports() -> set[str]:
    import mullion

    return set(mullion.__all__)


def _imported_from_mullion(tree: ast.AST) -> set[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "mullion"
        for alias in node.names
    }


def _names_used(tree: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def test_every_readme_example_parses() -> None:
    blocks = _python_blocks(_readme_named_by_pyproject().read_text())
    assert blocks, "no python examples found -- has the fence spelling changed?"
    for index, block in enumerate(blocks):
        try:
            ast.parse(block)
        except SyntaxError as exc:  # pragma: no cover - only on a broken README
            raise AssertionError(f"README example {index} does not parse: {exc}") from exc


def test_every_mullion_name_an_example_uses_was_imported_first() -> None:
    """A copied example has to run, and one of these did not.

    `0.2.0` shipped a quick start that called ``open_path`` and imported only
    ``contain, encode, open_bytes, watermark`` — a ``NameError`` for the first
    reader to paste it, on the page PyPI renders. Nothing caught it: it is
    prose to every linter, the wheel builds, and ``twine check`` validates that
    the markup renders rather than that the code works.

    Imports accumulate down the page, the way a reader accumulates them: a
    later block may use a name an earlier block imported, which is how the
    ``n_frames`` wrong/right pair is written. What it may not do is use an
    export that has been introduced nowhere.
    """
    exports = _exports()
    blocks = _python_blocks(_readme_named_by_pyproject().read_text())
    assert blocks, "no python examples found -- has the fence spelling changed?"

    seen: set[str] = set()
    offenders: list[str] = []
    for index, block in enumerate(blocks):
        tree = ast.parse(block)
        seen |= _imported_from_mullion(tree)
        for name in sorted((_names_used(tree) & exports) - seen):
            offenders.append(f"example {index}: {name}")

    assert offenders == [], (
        f"{offenders} are used in a README example before any example imports them. "
        "A reader who copies the block gets a NameError."
    )


def test_the_example_checker_catches_a_missing_import() -> None:
    """Guards the guard, with the exact defect that shipped in 0.2.0."""
    tree = ast.parse("from mullion import open_bytes\nopen_path(p)\n")
    used = _names_used(tree) & _exports()
    assert "open_path" in used
    assert "open_path" not in _imported_from_mullion(tree)
