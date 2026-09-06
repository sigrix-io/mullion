## What this changes

<!-- One or two sentences. The diff shows what changed; say why. -->

## Does it change output?

<!--
The question that matters most in a library that produces pixels. Delete the
rows that do not apply.

- [ ] No — refactor, docs, tests or tooling only.
- [ ] Yes, and it is a fix — the previous output was wrong. Say for which
      inputs, so the changelog entry can name them.
- [ ] Yes, and it is a default moving. CONTRIBUTING asks for the images:
      what got better, and what got worse. There is no threshold that is right
      for everything.
-->

## Have you watched the new tests fail?

<!--
CONTRIBUTING calls this the one house rule. Every defect this library addresses
is silent, so a test can assert the right thing about the right pixel and still
be worthless — break the implementation deliberately, confirm the test that
names the claim goes red, then put it back.

Say which mutation you tried and which test caught it.
-->

## Checks

- [ ] `python -m pytest`
- [ ] `python -m ruff check src/ tests/`
- [ ] `python -m ruff format --check src/ tests/`
- [ ] Scope: this still handles *one* image (see CONTRIBUTING)
- [ ] `CHANGELOG.md` updated under `Unreleased`, if this is user-visible
