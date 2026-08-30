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
