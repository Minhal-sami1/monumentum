# agentloop — the Loop standard

**Governed agent self-improvement.** An agent learns a lesson; the lesson
travels as a signed, evidence-backed, gated, journaled, reversible change —
or it does not travel at all.

Agent experience does not compound. A lesson either dies with the context or
persists ungoverned: an unchecked memory write or prompt edit with no
evidence, no gate, no audit trail, and no way to reach another agent. This
standard makes one self-modification **proven, gated, recorded, reversible,
and portable**.

Enforcement is deterministic code, never the model. A skill can *teach* the
loop; only code may *enforce* it.

> **Status: pre-release.** The working name is `agentloop`; the final
> protocol name is not settled. Nothing here has been published.

## Quick look

```bash
agentloop init                     # scaffold .loop/, write the AGENTS.md contract
agentloop propose --layer context --target AGENTS.md --patch lesson.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks."
agentloop evidence <cs-id> --record ev.json --artifact transcript.json
agentloop gate <cs-id> && agentloop apply <cs-id>
agentloop verify .                 # journal chain + managed files, one CI command
```

Full walkthrough: **[docs/QUICKSTART.md](docs/QUICKSTART.md)** (doc-tested by
`make quickstart-test`).

## Documentation

| Document | What it covers |
|---|---|
| [docs/README.md](docs/README.md) | Project overview, layout, all commands |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | The 10-minute consumer path |
| [spec/loop-spec.md](spec/loop-spec.md) | The normative specification, v0.1 |
| [conformance/README.md](conformance/README.md) | How any executor proves conformance |
| [adversarial/README.md](adversarial/README.md) | Threat model and executed attacks |
| [docs/REPRODUCE.md](docs/REPRODUCE.md) | Regenerating every number in the paper |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Every design deviation, with evidence |
| [docs/STATUS.md](docs/STATUS.md) | Milestone log and the final gate report |

## Build and verify

```bash
make setup     # venv + editable installs (CLI + SDK)
make verify    # schemas, conformance, tests, demo, scenarios,
               # adversarial suite, quickstart doc-test, dogfood, lint
```

Requires Python 3.11+, git, and Node (for one scenario fixture). On Windows,
pass an explicit interpreter if `python` is older: `make setup PY="py -3.11"`.

## Licenses

Code: **Apache-2.0** ([LICENSE](LICENSE)). Specification text:
**Community Specification License 1.0** ([LICENSE-SPEC.md](LICENSE-SPEC.md)).
