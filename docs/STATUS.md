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

## m3 — Two doors + interop demo (2026-08-31)

**Exit gate:** `make demo` — exit 0. One lesson crossed two runtimes (CLI door → SDK door) with both journals asserted; wall-clock lesson-to-second-runtime logged to `experiments/interop/logs/`.

Built:
- **B1 skill package:** `skill/SKILL.md` (assertive description, deterministic propose steps), `skill/hooks/pretooluse_guard.py` (PreToolUse deny on managed targets, exit-2 contract), `skill/hooks/stop_reminder.py` (Stop-hook queue reminder via systemMessage), `agentloop install-skill` (idempotent settings.json merge). Hook + skill mechanics verified against live docs first (DEC-017). Hook-denial HARD gate: `tests/test_hook.py`. Live `claude -p` trigger experiment deferred to experiments phase (DEC-022).
- **B2:** `agentloop init` appends the AGENTS.md managed contract block idempotently; double-init changes nothing (unit-tested).
- **B3 SDK:** `loop` package — `Loop(".loop")`, `propose`, `attach_evidence`, `gate`, `apply`, `rollback`, plus `log`, `ingest`, `approve`, `verify`; `sync` arrives at m4. Toy custom agent (~170 lines) in `sdk/examples/`.
- **B4:** `make demo` — scripted producer session drives the real CLI in repo A; toy SDK agent gates the lesson against its own policy and applies it to its own prompt file in workspace B; both end states + both journals asserted; interop time logged (2.3s in local runs).

Verified locally: `make verify` (schemas + conformance 15/15 + 121 tests + demo + lint) exit 0.

Next: m4 — Team-lite (sync over git remote, ed25519 signing, verify-on-pull) + dogfood starts.

## m4 — Team-lite + dogfood (2026-08-31)

**Exit gate:** `make scenarios` (UC1–UC3) + `agentloop verify .` — both exit 0 (locally and wired into `make verify` for CI).

Built:
- **C1 registry:** `agentloop sync` over a plain git remote — pushes PROMOTED ChangeSets, pulls peers'; a pulled ChangeSet enters PROPOSED and is validated/gated against LOCAL policy (never bypasses gates). `promote` verb added. Registry cache pins `core.autocrlf=false` (byte-stable digests, DEC-024).
- **C2 signing:** minisign-style detached ed25519 signatures (`agentloop keygen`, sign-at-push, verify-on-pull against trusted pubkeys). Unsigned, tampered, and untrusted-key ChangeSets are refused and journaled (I6). Full Sigstore is Team-full, not implemented (F4).
- **Scenarios:** `scenarios/run_all.sh` + UC1 (context lesson, real failing/passing commands, L2 auto-apply, next-session benefit), UC2 (capability repair, L1 queue honored, approve AND reject paths), UC3 (fleet propagation A→registry→B with local gating, propagation time logged ~10s, policy-violating pulled change refused in B). Artifacts under `scenarios/<id>/out/artifacts/`; JSONL run logs under `experiments/scenarios/logs/`.
- **Dogfood (from this tag):** this repo runs under its own `.loop/` — context = AGENTS.md/CLAUDE.md (L2), capability = `skill/**` (L1, Minhal approves), architecture = agents.yaml (L1). `agentloop verify .` runs in `make verify` and CI. Rules honored: no hand edits to `.loop/**`; all L1 items queue for Minhal.
- SDK gains `sync` + `promote`. Registry schema gains optional `signing` block (golden cases updated).

Verified locally: `make verify` (schemas + conformance 15/15 + 134 tests + demo + scenarios 3/3 + verify-self + lint) exit 0.

Next: m5 — UC4 (regression + ratchet-down) and UC5 (audit reconstruction); all five scenarios green.

## m5 — Battle tests complete (2026-08-31)

**Exit gate:** `make scenarios` — 5/5 green, artifacts regenerated under `scenarios/*/out/artifacts/`.

Built:
- **UC4 regression + ratchet-down:** two plausible capability "optimizations" auto-apply at L2 with verified-but-narrow independent evidence, each breaks the fixture's REAL pytest suite in the observation window, each rolls back to exact prior hashes; the second rollback de-escalates capability L2→L1 (journaled `policy_changed`); a third proposal then queues. Full 12-event journal sequence asserted.
- **UC5 audit reconstruction:** `scenarios/uc5/audit.py` (stdlib-only, no agentloop import) rebuilds — from the journal ALONE — the changes in effect with their rationales and actors, the reverted and refused changes with reasons, and the replayed autonomy levels; then cross-checks every journal-recorded target state against current file hashes and executor state. AUDIT OK asserted.
- Journal enriched for auditability (DEC-027): rationale + layer + targets on `proposed`, starting levels on genesis, structured ratchet transitions on `policy_changed`.

Verified locally: `make verify` (schemas + conformance + tests + demo + scenarios 5/5 + verify-self + lint) exit 0.

Next: m6 — adversarial suite (T1, T2, T4, T5, T6 + control).

## m6 — Adversarial suite (2026-08-31)

**Exit gate:** `make adversarial` — 7/7 pass, each attack passing BY being stopped/detected.

Built (each drives the real binary; nothing mocked):
- **T1** self-graded evidence at L2 → refused by I3, journaled.
- **T2** injected instruction → proposal to a non-allowlisted memory path → refused by I4, attempt journaled.
- **T3-lite** supply-chain tamper of a registry ChangeSet → refused on pull by ed25519 verification (Team-lite; full Sigstore is Governed, unimplemented).
- **T4** loop self-capture → (a) `.loop/policy.yaml` target refused (I1, schema layer, DEC-030); (b) hand-edited journal → `verify` fails (CI backstop).
- **T5** hostile-content capability backdoor → lands in L1 queue, never auto-applies, apply-without-approval refused, diff+rationale reviewable on disk.
- **T6** journal tampering → `verify` fails at the break point (I2).
- **control** legitimate well-evidenced change → passes the same gates and APPLIES (gates are not theater).

Run logs: `experiments/adversarial/logs/`. `adversarial/README.md` documents the threat→mitigation map.

Verified locally: `make verify` (schemas + conformance + tests + demo + scenarios 5/5 + adversarial 7/7 + verify-self + lint) exit 0.

Next: m7 — experiments framework, metrics, paper draft, publication hygiene.
