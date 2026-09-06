# Security Policy

Mullion decodes untrusted bytes. That is the whole of its attack surface and
it is worth naming plainly: every caller hands it a file somebody else chose.

## Reporting a vulnerability

**Do not open a public issue.**

Email **security@sigrix.io** with enough detail to reproduce, and attach the
input if you can. You will get an acknowledgement within 72 hours and an
assessment as soon as we have one. [CONTRIBUTING.md](CONTRIBUTING.md) publishes
the queues everything else waits in; security reports jump all of them.

## What is in scope

- **An input that makes this library do something a caller cannot defend
  against** — unbounded memory or time from a small file, a path that escapes
  the caller's control, an exception type that is not what the documented
  contract implies.
- **Anything that makes the safe spelling less safe than the unsafe one.** The
  argument of this library is that `open_bytes(data)` is a better answer than
  `Image.open(BytesIO(data)).convert("RGB")`. A way in which it is *worse* is
  the most valuable report we can receive.
- **Leaking through the output.** Metadata that should not survive
  normalization, or a code path that returns a caller another caller's pixels.
- **Defects in the repository itself**: the CI workflows, the packaging, the
  published wheel's contents.

## What is not in scope

- **Vulnerabilities in Pillow.** Report those to
  [python-pillow/Pillow](https://github.com/python-pillow/Pillow/security).
  If a Pillow weakness is *reachable in a way this library makes worse* — a
  default we chose, a guard we removed — that is in scope here; say so.
- **Decompression bombs, in the general case.** Pillow's own
  `Image.MAX_IMAGE_PIXELS` guard is active by default and this library does not
  raise or disable it. A path here that bypasses it *is* a finding.
- **Resource limits a caller must impose.** How large an upload to accept, and
  how long to allow, are the application's decisions and cannot be made from
  inside a decoding library.

## Supported versions

| Version | Status |
|---|---|
| 0.1.x | Pre-release — supported |

Mullion is pre-1.0, and [VERSIONING.md](VERSIONING.md) is blunt about what
that means: nothing is stable, and any `0.x` release may break any other. There
is no back-porting, because there is nothing to back-port to. A finding lands
in the next release with a [CHANGELOG.md](CHANGELOG.md) entry recording it.

## What happens next

We will agree a disclosure timeline with you rather than impose one, and the
changelog entry will credit you unless you would rather it did not.

This is a small team, and [CONTRIBUTING.md](CONTRIBUTING.md) is candid about
what that means everywhere else. Security is the one queue where the 72-hour
acknowledgement is a commitment rather than an aspiration.
