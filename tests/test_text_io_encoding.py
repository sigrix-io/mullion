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

Covers the builtin ``open`` as well as ``read_text``/``write_text``, which is
what put this rule on the AST. Both of the awkward cases are name collisions
that no pattern can resolve: ``open(`` is a suffix of ``Popen(`` and of every
identifier ending in ``_open``, and ``Image.open`` is Pillow's decoder, which
shares a method name with ``Path.open`` while putting a *file* where pathlib
puts a *mode*. It appears a dozen times here, including inside docstrings, and
every one of those is correct — a rule that flagged them would be turned off
rather than obeyed, so the rule reads what the call is rather than how it is
spelled, and leaves alone anything it cannot read.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: A file mode is drawn from this alphabet and nothing else, which is what
#: tells ``path.open("r")`` apart from ``Image.open("photo.png")``: both put a
#: string first, and only one of them is naming a mode.
_MODE = re.compile(r"^[rwxabt+]+$")

#: A mode that was computed rather than written down. Reported by nobody: see
#: _implicit_encoding_calls on why guessing costs more than missing.
_UNKNOWN = object()


def _named_mode(node: ast.Call, position: int) -> object:
    """The mode this call names, read from ``position`` or from ``mode=``."""
    mode = node.args[position] if len(node.args) > position else None
    for keyword in node.keywords:
        if keyword.arg == "mode":
            mode = keyword.value
    if mode is None:
        return None
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return mode.value
    return _UNKNOWN


def _implicit_encoding_calls(text: str) -> list[str]:
    """Every text-I/O call in ``text`` that does not name utf-8, with its line.

    Reads the AST rather than the characters. The builtin ``open`` is what
    forces it: textually ``open(`` is a suffix of ``Popen(`` and of every
    identifier ending in ``_open``, so a pattern that caught the call would
    catch those too, and a rule that fires on correct code gets switched off
    rather than obeyed.

    ``Image.open`` is the same problem from the other side, and it is why a
    first argument that is not a mode leaves the call alone. Pillow's decoder
    shares the method name with ``Path.open`` and puts a *file* where pathlib
    puts a *mode* — ``Image.open(path)``, ``Image.open(BytesIO(payload))``,
    and, if anyone writes it, ``Image.open("photo.png")``. Modes are drawn
    from ``rwxabt+`` and filenames are not, so the two are told apart by
    shape; anything else is left alone, because a guard that flagged a decoded
    PNG would be deleted within the week.

    ``Path.write_text`` requires the data to write, so a ``write_text()`` call
    with no positional argument is some other method of that name.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        # Never answer "clean" for a file that was never read: an empty list
        # from a parse failure is indistinguishable from one that holds.
        return [f"could not be parsed, so nothing was checked: {exc}"]

    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function = node.func
        if isinstance(function, ast.Name) and function.id == "open":
            name, mode = "open", _named_mode(node, 1)
        elif isinstance(function, ast.Attribute) and function.attr == "open":
            name, mode = "open", _named_mode(node, 0)
            if isinstance(mode, str) and not _MODE.match(mode):
                continue  # a filename, so not pathlib's open
        elif isinstance(function, ast.Attribute) and function.attr in {"read_text", "write_text"}:
            if function.attr == "write_text" and not node.args:
                continue
            name, mode = function.attr, None
        else:
            continue

        if mode is _UNKNOWN or (isinstance(mode, str) and "b" in mode):
            continue
        if any(keyword.arg == "encoding" for keyword in node.keywords):
            continue
        findings.append(f"{name}() without encoding, line {node.lineno}")
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
        ("open(path)", True),
        ('open(path, "r")', True),
        # Path.open() with no mode is text; Image.open needs a file, so a
        # no-argument .open() cannot be that one.
        ('Path("a").open()', True),
        ('Path("a").read_text(encoding="utf-8")', False),
        ('open(path, "wb")', False),
        ('open(path, encoding="utf-8")', False),
        ('Path("a").open("rb")', False),
        # The collisions that put this rule on the AST.
        ("Image.open(BytesIO(payload))", False),
        ("Image.open(path)", False),
        ('Image.open("photo.png")', False),
        ("subprocess.Popen(argv)", False),
        ("report.write_text()", False),
    ],
)
def test_the_sweep_still_has_teeth(source: str, flagged: bool) -> None:
    """A guard that has never failed and one that cannot fail read the same."""
    assert bool(_implicit_encoding_calls(source)) is flagged
