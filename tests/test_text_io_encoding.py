"""Text I/O in this repository names its encoding, because the default is not UTF-8.

``Path.read_text()`` with no ``encoding`` decodes using the locale's preferred
encoding, which is cp1252 on a Windows contributor's machine and ASCII under
``LC_ALL=C``. Every file this repository reads is UTF-8, so the omission is a
bug wherever the bytes are not plain ASCII — and this README and
``pyproject.toml`` both carry em dashes.

What makes it worth a guard rather than a habit is that the two failures look
nothing alike. cp1252 *decodes* an em dash into mojibake and the test reads a
corrupted document while passing, because the assertions are on ASCII URLs and
filenames; ASCII *refuses* it and the same test dies with
``UnicodeDecodeError``. So a green suite on Linux says nothing about either,
and which one a contributor meets depends only on which characters happen to
be in the file that day. Measured 2026-09-16, before the fix: the four
``test_packaging`` cases pass here and fail under ``LC_ALL=C``.

Scoped to ``read_text``/``write_text`` on purpose. The obvious third member,
``.open(``, cannot be swept textually in this repository — ``Image.open`` is
Pillow's decoder, it is binary, it appears a dozen times including inside
docstrings, and every one of those is correct. A rule that flagged them would
be turned off rather than obeyed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: The calls whose default encoding comes from the locale rather than the file.
_TEXT_IO_CALLS = ("read_text(", "write_text(")


def _implicit_encoding_calls(text: str) -> list[str]:
    """Every text-I/O call in ``text`` that does not name utf-8, with its line."""
    findings: list[str] = []
    for call in _TEXT_IO_CALLS:
        index = 0
        while True:
            position = text.find(call, index)
            if position == -1:
                break
            if "utf-8" not in text[position : position + 200]:
                line = text.count("\n", 0, position) + 1
                findings.append(f"{call}) without encoding, line {line}")
            index = position + len(call)
    return findings


def _python_sources() -> list[Path]:
    return sorted(
        path
        for directory in ("src", "tests")
        for path in (ROOT / directory).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def test_every_text_read_and_write_names_utf8() -> None:
    offenders: list[str] = []
    for path in _python_sources():
        # This module quotes the call names in _TEXT_IO_CALLS, so it matches itself.
        if path.name == Path(__file__).name:
            continue
        for finding in _implicit_encoding_calls(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(ROOT)}: {finding}")

    listed = "\n  - ".join(offenders)
    assert offenders == [], f"text I/O that decodes with the locale's encoding:\n  - {listed}"


def test_the_sweep_read_something_to_sweep() -> None:
    """A sweep over an empty file list and a clean tree read identically."""
    sources = _python_sources()
    assert len(sources) > 5, f"only {len(sources)} sources found; the rglob went stale"
    assert any(path.name == "test_packaging.py" for path in sources), (
        "test_packaging.py is the file that reads repo files, and the sweep did not see it"
    )


@pytest.mark.parametrize(
    ("source", "flagged"),
    [
        ('Path("a").read_text()', True),
        ('Path("a").write_text(body)', True),
        ('Path("a").read_text(encoding="utf-8")', False),
        ("Image.open(BytesIO(payload))", False),
    ],
)
def test_the_sweep_still_has_teeth(source: str, flagged: bool) -> None:
    """A guard that has never failed and one that cannot fail read the same."""
    assert bool(_implicit_encoding_calls(source)) is flagged
