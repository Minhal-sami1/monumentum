# agentloop

Reference implementation of the **Loop standard**: governed agent self-improvement.

Agent experience does not compound. Lessons die with the context, or they persist ungoverned — no evidence, no gate, no audit trail, no way to reach another agent. The Loop standard makes an agent's self-modification **proven, gated, recorded, reversible, and portable**: a ChangeSet carries the change, Evidence proves it, Policy gates it, the hash-chained Journal records it, and a Registry moves it across the fleet.

> Status: pre-release, milestone m1 (spec v0.1 + schemas + conformance skeleton).
> The 10-minute consumer quickstart lands with milestone m3.

## Layout

- `spec/` — the normative spec (`loop-spec.md`) and the five JSON Schemas
- `src/agentloop/` — the reference Executor CLI and library
- `conformance/` — golden-file conformance suite
- `docs/` — status, decisions, reproduce instructions

## Develop

```
make setup          # venv + editable install with dev deps
make check-schemas  # m1 gate: golden corpus against the normative schemas
make test           # unit tests
make verify         # everything that currently exists
```

On Windows, pass a 3.11+ interpreter explicitly if `python` is older: `make setup PY="py -3.11"`.

## Licenses

Code: Apache-2.0 (`LICENSE`). Spec text: Community Specification License 1.0 (`LICENSE-SPEC.md`).
