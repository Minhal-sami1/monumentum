# STATUS.md — milestone log

## m1 — Spec v0.1 + schemas + validator + conformance skeleton (2026-08-30)

**Exit gate:** `make check-schemas` — exit 0.
**Result:** 19 valid golden files validate; 23 required-failure golden files fail validation correctly; 0 problems.

Built:
- `spec/loop-spec.md` — spec v0.1, 14 sections per design-doc §10, RFC 2119 language, Governed marked "specified, not implemented in v1".
- `spec/schemas/` — five normative JSON Schemas (changeset, evidence, policy, journal-entry, registry), draft 2020-12.
- `src/agentloop/` — package skeleton: schema loader/validator, `agentloop check-schemas` CLI (alias `loop`).
- `conformance/golden/` — schema-level golden corpus, valid + REQUIRED-FAILURE cases per object type.
- `tests/` — 68 unit tests (schema compile, full corpus, edge cases, checker semantics, CLI).
- `Makefile` (setup, check-schemas, test, lint, verify), `.github/workflows/ci.yml`, licenses per F3.
- `docs/DECISIONS.md` — DEC-001..DEC-009.

Also verified locally: `make verify` (check-schemas + pytest + ruff) exit 0.

Next: m2 — reference Executor verbs + hash-chained journal + executor-level conformance suite.

## m2 — Reference Executor + executor-level conformance (2026-08-30)

**Exit gate:** `make conformance` — exit 0. 15/15 cases pass against the real CLI via the subprocess driver.

Built:
- Executor verbs: `init, propose, evidence, gate, apply, approve, reject, rollback, log, verify, status` (`agentloop`, alias `loop`).
- Hash-chained NDJSON journal with canonical serialization; genesis anchor; tail protected by `state.json` journal head (DEC-015).
- Deterministic gates: `evidence_required`, `reproducible_check` (post-apply with auto-revert, DEC-010/011), `human_review` queue with reviewer-identity enforcement; invariant I3 enforced on every L2/L3 auto path.
- Strict unified-diff applier (create/modify/delete, exact context); folder payloads; opaque payloads journal-only (D2).
- Snapshot-based rollback restoring exact prior hashes; automatic de-escalation with `policy_changed` journaling (A5).
- `verify`: chain integrity naming the first broken seq (A6), tail-truncation detection, managed-file drift detection from baseline heads (T4 backstop).
- Conformance runner (`conformance/runner.py`, executor-agnostic subprocess driver), 15 golden cases c01–c15, broken-executor stub failing the suite (D2 negative test).
- 104 unit tests; ruff clean.

Also verified locally: `make verify` (check-schemas + conformance + pytest + lint) exit 0.

Next: m3 — two doors: drop-in skill, AGENTS.md managed block, SDK five verbs, toy agent, interop demo.
