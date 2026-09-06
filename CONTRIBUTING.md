# Contributing

Thank you for looking. This document is deliberately blunt about what you can
expect, because a contribution guide that implies a service level nobody
staffed is worse than no guide at all.

## What to expect

**This library is maintained by a very small team.** That shapes everything
below, and it is better said once here than discovered issue by issue.

| | Realistic expectation |
|---|---|
| **Security reports** | Acknowledged within 72 hours. These jump every queue. |
| **Issues** | Read within a week. A reply may be "noted, not soon." |
| **Pull requests** | Reviewed within two weeks, often longer for anything that changes output. |
| **Silence** | Means the queue, not a verdict. Ping the thread. |

Merging is discretionary and stays with the maintainers. Contributions are
genuinely welcome; governance is not open. If that trade is not for you,
Apache-2.0 means you can fork this and go — no hard feelings, and please tell
us what we got wrong.

## Reporting a security issue

**Do not open a public issue.** Email **security@sigrix.io**, and expect an
acknowledgement within 72 hours. [SECURITY.md](SECURITY.md) is the full policy.

The part worth repeating here: this library decodes untrusted bytes, so an
input that makes it misbehave is in scope even if the misbehaviour is Pillow's
— tell us, and we will work out together whose it is.

## What belongs here, and what does not

The scope is narrow on purpose, and a pull request that widens it will be
turned down however good it is. [The README says what is out of
scope](README.md#what-it-is-not); the line is this:

> **This library handles one image. Composing several is the application's job.**

Resizing, cropping, format conversion, colour management and model-based
background removal are all deliberately absent. Pillow already does the first
three well, and a thin correctness layer that grows into a second imaging
toolkit stops being adoptable — an application takes this on because it is
small.

What does belong: another way an image arrives wrong and is silently accepted.
That is the whole thesis, and if you have hit one we have not, it is the most
useful thing you can bring.

## Before opening an issue

The tracker has a form for each of three kinds, because they are triaged
differently. Pick the one that fits and the form will ask for what that kind
needs.

- **A defect.** An image comes out wrong, or a documented behaviour is not the
  behaviour. **Attach the input**, or say precisely how to construct it — see
  below.
- **A change.** You want Mullion to do something it does not. Read the scope
  section above first.
- **"I depend on this."** Not a defect, and very welcome anyway. Knowing who is
  building on `0.x` is what lets us avoid breaking you silently — see
  [VERSIONING.md](VERSIONING.md).

There is no blank issue, and that is not a filter — all three are welcome. It
is that "which of these is it" is the question the queue is sorted by, and
asking it on the way in costs you one click and saves a round trip.

## Reporting an image defect

**Attach the image, or the code that builds it.** This is asked for more firmly
here than in most projects, and the reason is the reason the library exists: a
wrong answer here renders as a *plausible picture*. "The background looks wrong"
cannot be acted on, because every implementation in the space produces a
plausible picture for some input and the whole question is which input.

If you cannot share the file — it is a customer's, it is confidential — a
constructing snippet is just as good and often better:

```python
from PIL import Image
image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
# ...the specific thing that makes it awkward
```

Every fixture in [`tests/conftest.py`](tests/conftest.py) is built that way,
for exactly this reason: a reader can see what makes each image awkward, which
a committed binary hides.

## Working on the code

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src/ tests/
python -m ruff format --check src/ tests/
```

All four before you push. CI runs the same commands, and the two ruff ones run
*before* the tests — a formatting slip fails the job before a single test
executes.

### A test has to be able to fail

This is the one house rule worth stating outright, because the alternative is
subtle enough to survive review.

Every defect this library addresses is silent. That means a test can assert the
right thing about the right pixel and still be worthless. The real example, from
this repository's own history: the test for "an enclosed near-white highlight
survives" originally used a **pure white** highlight and asserted the result was
white — and it passed against a global-threshold implementation, because
cleaning a white pixel to white changes nothing. Making the highlight off-white
is what gave the assertion something to catch.

So, for anything that touches pixels:

- **Watch your test fail.** Break the implementation deliberately, confirm the
  test that names the claim goes red, then put it back. If nothing goes red, the
  test is decorative.
- **State the wrong answer next to the right one** where you can.
  `test_a_bare_convert_really_does_produce_black` exists purely so that the
  assertions after it mean something.
- **Prefer an assertion that distinguishes two implementations** over one that
  merely describes the output.

### Docstrings carry the reasoning

The modules here are commented heavily by most standards, and it is deliberate:
each explains *why* the obvious implementation is wrong. That explanation is the
durable part — the code is a page long and could be rewritten in an afternoon,
whereas the knowledge of what breaks silently took real images to acquire. A
pull request that improves the code and deletes the reasoning is a net loss.

## Proposing a change to a default

The tolerances in `background.py` are tuned against a finite set of real images,
so they will move. A pull request that moves one needs the images: what got
better, and — the half that is usually missing — **what got worse**. There is no
threshold that is right for everything, which is why the parameter is exposed at
all.
