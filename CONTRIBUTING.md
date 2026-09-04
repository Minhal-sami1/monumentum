# Contributing to Monumentum

Thank you for helping. This file tells you how to set up, how to verify,
and how changes reach the repository.

## Set up

```
make setup          # venv + editable installs (CLI and SDK)
make verify         # the full offline gate; it MUST exit 0 before you open a PR
```

Requirements: Python 3.11+, git, Node (one scenario fixture). `make paper`
also needs a LaTeX engine (Tectonic, `latexmk`, or `pdflatex`).

## What `make verify` checks

Schema corpus, unit tests, the conformance suite, the interop demo, all five
scenarios, the adversarial suite, the quickstart doc-test, this repository's
own journal (`monumentum verify .`), and lint. Do not skip, mute, or `xfail`
a failing test to make it pass. Fix the cause.

## This repository governs itself

Some files are **monumentum-managed** (see `.monumentum/policy.yaml`):
`AGENTS.md`, `CLAUDE.md`, and `skill/**`. Do not edit them directly. Propose
a ChangeSet instead:

```
monumentum propose --layer context --target AGENTS.md --patch fix.patch --rationale "<why>"
monumentum evidence <cs-id> --record ev.json --artifact transcript.json
monumentum gate <cs-id>
```

Context changes auto-apply with independent evidence. Capability changes
(`skill/**`) queue for the maintainer. `monumentum verify .` runs in CI and
fails the build on any ungoverned edit to a managed file.

## Changing the specification

The spec (`spec/`) and its five schemas are normative. A change to protocol
semantics MUST come with: the spec text, the schema, a golden conformance
case (including a required-failure case where a rule is added), and an entry
in `docs/DECISIONS.md` that states what changed, why, and the evidence.

## Implementing an executor

Run the conformance suite against your implementation through the
subprocess contract described in `conformance/README.md`. The reference CLI
passes it; a deliberately broken executor fails it. Yours must pass it to
claim conformance.

## Style

Prose follows ASD-STE100 principles: short sentences, active voice, one
idea per sentence. Normative statements use RFC 2119 keywords.

## Licenses

By contributing you agree that code contributions are licensed under
Apache-2.0 (`LICENSE`) and specification text under the Community
Specification License 1.0 (`LICENSE-SPEC.md`).
