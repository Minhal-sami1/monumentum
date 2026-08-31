# agentloop

Reference implementation of **the Loop standard**: governed agent self-improvement.

Agent experience does not compound. A lesson either dies with the context or
persists ungoverned — an unchecked memory write or prompt edit with no
evidence, no gate, no audit trail, and no way to reach another agent. The Loop
standard makes one self-modification **proven, gated, recorded, reversible,
and portable**: a ChangeSet carries the change, Evidence proves it, Policy
gates it, a hash-chained Journal records it, and a Registry moves it across a
fleet.

Enforcement is deterministic code, never the model. A skill can *teach* the
loop; only code may *enforce* it.

## 10-minute path

See [QUICKSTART.md](QUICKSTART.md) — doc-tested by `make quickstart-test`.

```
pip install -e .
agentloop init                      # scaffold .loop/, write the AGENTS.md block
agentloop propose --layer context --target AGENTS.md --patch lesson.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks."
agentloop evidence <cs-id> --record ev.json --artifact transcript.json
agentloop gate <cs-id> && agentloop apply <cs-id>
agentloop verify .                  # journal chain + managed files
```

Claude Code users also run `agentloop install-skill` to get the skill and a
`PreToolUse` hook that denies direct edits to managed files.

## What is here

| Path | What |
|---|---|
| `spec/` | Normative spec v0.1 (14 sections) + the five JSON Schemas |
| `src/agentloop/` | Reference Executor: CLI + library |
| `sdk/` | Python SDK (five verbs) + a toy custom agent |
| `skill/` | Drop-in Claude Code skill + hooks |
| `conformance/` | Golden corpus + executor-level suite for ANY executor |
| `scenarios/` | UC1–UC5 battle tests (real binary, headless) |
| `adversarial/` | Executed attacks T1–T6 + a control |
| `experiments/` | Runners, JSONL logs, metric aggregation |
| `paper/` | LaTeX source; every number generated from logs |
| `demo/` | "One lesson, two runtimes" |
| `.loop/` | This repo's own loop (dogfood) |

## Commands

```
make setup            # venv + editable install (CLI + SDK)
make verify           # the full gate: schemas, conformance, tests, demo,
                      # scenarios, adversarial, quickstart, verify-self, lint
make conformance      # executor-level suite against the reference CLI
make scenarios        # UC1–UC5
make adversarial      # T1–T6 + control (each passes BY being stopped)
make demo             # one lesson, two runtimes
make reproduce        # re-run every experiment, regenerate metrics
make paper            # build the PDF from generated tables
```

On Windows pass an explicit interpreter if `python` is older than 3.11:
`make setup PY="py -3.11"`.

Requirements: Python 3.11+, git, and Node (one scenario fixture runs a real
`node` script). `make paper` additionally needs a LaTeX engine — Tectonic
(preferred), `latexmk`, or `pdflatex`; it is not part of `make verify`, so
the gate runs without a TeX toolchain.

`make reproduce REPRODUCE_ARGS="--with-trigger"` additionally runs the
live-model skill-trigger experiment (needs the `claude` CLI and API access;
excluded from `make verify`, which must run offline in CI).

## Conformance

An executor claims conformance by passing `conformance/` through the
documented subprocess contract — see [conformance/README.md](../conformance/README.md).
The suite includes required-failure cases and a deliberately broken executor
stub that MUST fail.

## Status and decisions

- [STATUS.md](STATUS.md) — milestone log, gate-by-gate
- [DECISIONS.md](DECISIONS.md) — every deviation from the design doc, with evidence
- [REPRODUCE.md](REPRODUCE.md) — how to regenerate every number
- [../BLOCKERS.md](../BLOCKERS.md) — open blockers (empty means none)

## Licenses

Code: Apache-2.0 (`LICENSE`). Spec text: Community Specification License 1.0
(`LICENSE-SPEC.md`).
