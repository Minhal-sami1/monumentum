# DECISIONS.md — deviations and design decisions

Every deviation from `design-doc.md` normative semantics is recorded here with evidence. Format: what changed, why, evidence.

## m1

### DEC-001: `genesis` journal event added
- **What:** The journal event enum gains `genesis`. Entry `seq: 0` is the genesis entry with `prev: null`; it records the initial policy hash.
- **Why:** GOAL.md story A1 requires "an empty journal with a genesis entry". design-doc §5.4 lists events but no genesis. The hash chain needs a defined anchor.
- **Evidence:** `spec/schemas/journal-entry.schema.json` genesis rules; golden files `journal-entry/valid/genesis.json`, `invalid/bad-genesis-*.json`; tests `test_journal_genesis_rules`.

### DEC-002: uniform hash format `sha256:<64 lowercase hex>` everywhere
- **What:** All content hashes (ChangeSet payload, Evidence artifact, journal prev/target_state/policy) use the self-describing `sha256:` prefix.
- **Why:** design-doc sketches mix bare hex (§5.1 payload) and prefixed (§5.4 journal). One format removes ambiguity for independent implementations and keeps the door open for future hash agility. Field names unchanged; F5 allows representation refinement.
- **Evidence:** `$defs.hash` in all five schemas; golden corpus.

### DEC-003: path hygiene and I1 enforced at schema level too
- **What:** The ChangeSet schema itself rejects targets that are absolute, contain `..`, use backslashes or drive letters, or point into `.loop/`.
- **Why:** design-doc places allowlist/protected checks in the Executor (VALIDATED). Schema-level rejection is defense in depth: a conformant validator refuses T4-style ChangeSets even before executor logic runs. Executor still enforces I1/I4 (allowlists are policy-dependent; schema cannot know `targets_allow`).
- **Evidence:** `changeset.schema.json` `$defs.target_path`; `golden/changeset/invalid/bad-target-loop.json`, `bad-traversal-target.json`; tests.

### DEC-004: closed roots + `ext` extension container
- **What:** All five object roots set `additionalProperties: false`. Non-standard fields MUST go in an `ext` object.
- **Why:** Closed roots make required-failure conformance cases meaningful (typo'd field names fail loudly) and keep golden files byte-predictable. `ext` preserves extensibility without polluting the namespace.
- **Evidence:** all schemas; `golden/changeset/invalid/bad-unknown-field.json`.

### DEC-005: evidence artifact required per format
- **What:** `artifact` is REQUIRED for `inspect-log`, `lm-eval`, `otel-genai`, `command-transcript`; OPTIONAL for `human-feedback`.
- **Why:** Machine evidence without the raw artifact is unverifiable (violates the spirit of D4/I3). Human feedback can be self-contained in `summary`.
- **Evidence:** `evidence.schema.json` if/then; `golden/evidence/invalid/bad-transcript-no-artifact.json`.

### DEC-006: evidence list may be empty at PROPOSED
- **What:** ChangeSet `evidence: []` is schema-valid. Gates (`evidence_required`) enforce non-empty before APPLIED.
- **Why:** design-doc §8.2 SDK flow attaches evidence after propose. Schema validity must not block the propose step; D4 ("no change applies without evidence") is an apply-time rule.
- **Evidence:** spec §5, §6 rule 1; `golden/changeset/valid/cs-minimal.json`.

### DEC-007: registry v0.1 kind fixed to `git-remote`
- **What:** `registry.schema.json` allows only `kind: git-remote`. OCI is marked specified-not-implemented.
- **Why:** F4 fixes Team-lite scope. A closed kind makes the required-failure case (`bad-kind-oci.yaml`) enforceable.
- **Evidence:** schema; spec §10.1.

### DEC-008: `rejected` covers validation failure and gate rejection
- **What:** No separate `validated` journal event. `rejected` entries carry `decision.reason`.
- **Why:** design-doc §5.4 event list has no `validated` event; successful validation is implied by later events. Matches GOAL A2 ("journal records the rejection").
- **Evidence:** spec §8.3, §9; `golden/journal-entry/valid/rejected.json`.

### DEC-009: escalation/de-escalation change the *effective* level, not policy.yaml
- **What:** The Executor records effective-level transitions as `policy_changed` journal entries and tracks the effective level in `state.json`. It never rewrites `policy.yaml` (I1: only humans change it).
- **Why:** design-doc requires both "only a human may change policy.yaml" and "de-escalation is automatic". The only consistent reading: declared policy is human-owned; the effective level is executor state, journaled. GOAL A5 confirms: "journaled as `policy-effective` change".
- **Evidence:** spec §7.4; `golden/journal-entry/valid/policy-changed.json`.

## m2

### DEC-010: reproducible_check runs post-apply, with automatic revert
- **What:** The `reproducible_check` gate executes the transcript's `check_cmd` AFTER the payload is applied (snapshot taken first). Failure restores the snapshot and journals `rejected`.
- **Why:** The check proves the change works in place ("apply, run it again"). Running it pre-apply would test nothing. design-doc §8.1 walkthrough: "The CLI verifies the transcript is reproducible, applies the diff, journals" — the verification and the apply are one atomic step with revert-on-failure.
- **Evidence:** `executor.apply_changeset`; conformance `c02` (passes) and `c14` (fails and reverts); `tests/test_executor.py::test_reproducible_check_failure_reverts`.

### DEC-011: machine-checkable command-transcript artifact format
- **What:** A `command-transcript` artifact is JSON: `{"check_cmd": str, "runs": [{"phase": "before"|"after", "exit_code": int}]}`. The executor re-runs `check_cmd` and requires exit 0.
- **Why:** design-doc describes the transcript informally. Reproducibility needs a machine-readable command. Free-text transcripts fail the gate ("not machine-checkable"), which is the safe direction.
- **Evidence:** `executor._reproducible_check`; conformance c02/c14 fixtures.

### DEC-012: target_state hashes cover the whole target set
- **What:** `target_state.before/after` in `applied`/`rolled_back` entries is one hash: sha256 over the canonical JSON of sorted `[target, filehash|null]` pairs. Per-target hashes live in `state.json`.
- **Why:** The journal-entry schema has one before/after slot; ChangeSets may touch several files. One combined deterministic hash keeps the schema and gives auditors an exact-state commitment.
- **Evidence:** `executor._combined_hash`; rollback restores and re-verifies per-target hashes from the snapshot manifest.

### DEC-013: CLI exit codes 0/1/2 are the conformance driver contract
- **What:** 0 success, 1 rejected/failed, 2 queued (gate) or usage error. Documented in `conformance/README.md`; the runner enforces them.
- **Why:** D2 requires a subprocess contract any executor can implement. Exit codes are the cheapest portable signal.
- **Evidence:** `conformance/runner.py`, all 15 cases, broken-stub negative test.

### DEC-014: approve applies immediately
- **What:** `agentloop approve <id> --actor reviewer/x` journals `approved` and then runs apply in the same command.
- **Why:** GOAL A4: "`agentloop approve <id>` as reviewer → applied". A separate apply step after approval adds a state with no reviewer value.
- **Evidence:** `executor.approve`; conformance c07.

### DEC-015: journal tail protected via state.json head hash
- **What:** `state.json` records `journal_head` = hash of the newest journal line. `verify` checks it alongside the chain.
- **Why:** A hash chain cannot protect its own last line (truncation or tail edit leaves a valid shorter chain). The head hash closes that hole; Governed closes it fully with a transparency log.
- **Evidence:** `tests/test_executor.py::test_verify_detects_tail_truncation`.

### DEC-016: policy escalation block accepted but not executed in v1
- **What:** The `escalation` policy block validates against the schema, but the v1 executor never raises a level automatically. De-escalation IS implemented.
- **Why:** No GOAL story or gate exercises escalation; auto-raising autonomy without a tested track-record window is exactly the kind of silent power creep the standard exists to stop. Spec §7.4 says MAY.
- **Evidence:** spec §7.4; `executor._maybe_de_escalate` (no escalation counterpart); documented here.
