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

## m3

### DEC-017: Claude Code hook and skill mechanics verified against live docs (GOAL B1 requirement)
- **What:** Verified on 2026-08-30 against https://code.claude.com/docs/en/hooks and https://code.claude.com/docs/en/skills (docs.claude.com redirects there).
- **Verified hook API:** hooks configured in `.claude/settings.json` under `hooks.PreToolUse` as `[{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": ...}]}]`; matcher filters on `tool_name` (pipe-separated alternatives, regex allowed). The hook receives JSON on stdin with `hook_event_name`, `tool_name`, `tool_input` (for Edit/Write: contains `file_path`), `cwd`, `session_id`. Blocking: exit code 2 always blocks, stderr text is shown to Claude as the block reason; alternatively exit 0 with JSON `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": ...}}`. `Stop` hook fires when Claude finishes a turn; exit 2 blocks stopping. `SessionEnd` cannot block and has a short shared timeout — the design-doc §8.1 "Stop/session-end reminder" is therefore implemented on `Stop`.
- **Verified skill API:** skills live at `.claude/skills/<name>/SKILL.md`; YAML frontmatter fields `name`, `description` (combined with `when_to_use`, truncated at 1,536 chars in the listing; Claude uses it to decide when to load), `allowed-tools`, `disable-model-invocation`; `${CLAUDE_SKILL_DIR}` expands in skill body and in `allowed-tools` Bash rules, which is the documented pattern for bundled `scripts/`.
- **Evidence:** fetched pages 2026-08-30; hook stdin/exit-code contract exercised by `tests/test_hook.py`.

### DEC-018: PreToolUse guard reads managed patterns from state.json
- **What:** The hook script (`skill/hooks/pretooluse_guard.py`, stdlib-only) denies Edit/Write on paths matching the policy's `targets_allow` + `protected` patterns. It reads `.loop/state.json` (`managed_patterns`, written by the executor at init and policy load) and falls back to parsing policy.yaml only if PyYAML is importable.
- **Why:** The hook must run under any system Python with zero dependencies; policy.yaml needs a YAML parser. state.json is executor-owned JSON and already the effective-state carrier (DEC-009).
- **Evidence:** `skill/hooks/pretooluse_guard.py`; `tests/test_hook.py`.

### DEC-019: the toy agent translates a foreign lesson instead of replaying the foreign diff
- **What:** In the interop demo, runtime B's toy agent reads the foreign ChangeSet's rationale and proposes a NEW ChangeSet against its own prompt file (`prompts/system.md`), with its own reproducible evidence, gated by its own policy.
- **Why:** design-doc §8.4: the second runtime "applies it to its own prompt file". The foreign diff targets AGENTS.md; replaying it would change the wrong surface. Translation is the Producer-adapter pattern (§8.3) and proves real interop: the LESSON crosses runtimes, each executor gates locally.
- **Evidence:** `sdk/examples/toy_agent.py cmd_ingest`; `demo/run_demo.py` assertions on both journals.

### DEC-020: Core-profile handoff = the ChangeSet folder travels as files
- **What:** The demo moves the ChangeSet by copying its folder (minus the runtime-local `snapshot/`) from A to B. No registry, no signing at m3.
- **Why:** Core profile is files-first (design principle 1). The git-remote registry with ed25519 signing is exactly the m4 deliverable; the demo proves portability at the file-plane level first.
- **Evidence:** `demo/run_demo.py` handoff step; B journals its own proposed/gated/applied sequence.

### DEC-021: session reminder implemented on Stop via systemMessage
- **What:** The reminder hook runs on `Stop` and emits `{"systemMessage": ...}` listing queued ChangeSets; it never blocks the stop.
- **Why:** Verified docs (DEC-017): Stop stdout is not shown to Claude; exit 2 would block every session end; SessionEnd cannot surface messages reliably (short shared timeout, no decision fields). `systemMessage` reaches the user — the actor who can approve L1 items — which is the reminder's audience.
- **Evidence:** `skill/hooks/stop_reminder.py`; `tests/test_hook.py::test_reminder_reports_queued_changesets`.

### DEC-022: B1 live trigger-rate experiment deferred to the experiments phase
- **What:** The hook-denial test and the full happy path (both HARD gates) are covered by deterministic tests at m3 (`tests/test_hook.py`, conformance c02, `make demo`). The ≥5 headless `claude -p` trigger-reliability runs (soft floor 70%) are scheduled with `experiments/trigger/` (m5–m7), where run logging exists to report the rate.
- **Why:** GOAL B1 marks the trigger rate as a REPORTED metric, not a gate; the experiments framework (E1) that must log those runs lands after the scenarios.
- **Evidence:** this entry; `docs/STATUS.md` m3 notes.

## m4

### DEC-023: registry sync semantics — pull enters PROPOSED; refusal vs rejection
- **What:** `sync` pushes locally PROMOTED ChangeSets (signing them at push) and pulls unknown ones. A pulled ChangeSet is signature-verified FIRST (I6), then runs the normal PROPOSED→VALIDATED path against LOCAL policy; gate/apply are separate explicit steps. Exit code: 1 only for security refusals (unsigned/tampered/untrusted); policy-validation rejections of pulled changes are normal outcomes (journaled `rejected`, exit 0).
- **Why:** "Distribution never bypasses gates" (design §5.5); a peer's policy legitimately differs, so an I4 rejection in B is the system working, not a sync failure. Security refusals are attacks and must be loud.
- **Evidence:** `registry.sync`; `tests/test_registry.py`; scenario UC3 (policy-violating pulled change refused in B, journaled).

### DEC-024: registry cache pins core.autocrlf=false
- **What:** The registry clone under `.loop/cache/registry` is created with `core.autocrlf=false, core.eol=lf`.
- **Why:** Detached signatures cover exact bytes. A host git config that rewrites line endings on checkout would break every digest cross-platform (observed on Windows during development).
- **Evidence:** `registry._ensure_cache`; `tests/test_registry.py::test_push_and_pull_with_local_gating` passes on Windows.

### DEC-025: signing config lives in registry.yaml; keys never travel
- **What:** `registry.yaml` gained an optional `signing: {key_file, signer}` block (schema updated + golden cases). Private keys live under `.loop/keys/` and are never copied by sync; only `*.pub` files are distributed to peers' `pubkeys_dir`.
- **Why:** Team-lite (F4) needs a place to say "sign pushes with this key". The registry schema is the natural carrier; minisign-style raw-hex ed25519 keys keep it dependency-light (`cryptography` runtime only).
- **Evidence:** `spec/schemas/registry.schema.json`; `signing.py`; golden `registry/valid/git-remote.yaml`, `invalid/bad-signing-no-signer.yaml`.

### DEC-026: dogfood policy scope for this repository
- **What:** This repo's own `.loop/policy.yaml` governs: context = AGENTS.md, CLAUDE.md (L2); capability = `skill/**` (L1, Minhal-only approval); architecture = `agents.yaml` (L1). `docs/**`, source, tests, spec are NOT loop-managed.
- **Why:** The managed surface is what steers agents (design principle 3). STATUS/DECISIONS are project logs the goal REQUIRES updating continuously; making them loop-managed would gate documentation behind review and stall the milestones. The skill package is the repo's real capability layer.
- **Evidence:** `.loop/policy.yaml`; `agentloop verify .` green in `make verify` and CI.

## m5

### DEC-027: journal entries enriched so the journal is audit-self-contained
- **What:** `proposed` entries carry `note` = the ChangeSet rationale and `ext.layer`/`ext.targets`; the genesis entry carries `ext.effective_levels` (starting levels); `policy_changed` carries `ext.policy_effective {layer, from, to}`.
- **Why:** The audit promise (design §5.4): reconstruct WHY a workspace behaves as it does from the Journal ALONE. Without rationale, targets, and starting levels in the journal, an auditor would need the changesets folder and the policy — breaking "journal alone". All additions live in the schema's `note`/`ext` fields; no schema change.
- **Evidence:** `executor.propose`, `init_workspace`, `_maybe_de_escalate`; `scenarios/uc5/audit.py` reconstructs rationale, actors, ratchet history, and levels from journal files only, then passes the reality check.

### DEC-028: UC4 exercises detection through a real test suite, ratchet via two auto-applied regressions
- **What:** UC4's policy puts capability at L2 with evidence-only gates, so two plausible "optimizations" (each carrying verified, independent, but narrow evidence) auto-apply and each breaks the fixture's real pytest suite; each is rolled back; the second rollback trips de-escalation to L1; a third proposal then QUEUES.
- **Why:** GOAL UC4 needs "an applied change breaks a real test in the observation window" plus the ratchet. Narrow-but-genuine evidence passing the gate while the full suite fails is exactly the honest failure mode the observation window exists for.
- **Evidence:** `scenarios/uc4/` (pytest output captured in artifacts; journal asserts the full 12-event sequence including `policy_changed`).

### DEC-029: UC1 fixture reproduces the npm/pnpm failure class deterministically
- **What:** The UC1 fixture is a real npm package whose postinstall (`node install.js`) exits 1 under npm semantics and 0 under pnpm semantics, driven headless via `node install.js npm|pnpm` instead of running real package installs.
- **Why:** Real `npm install`/`pnpm install` would need network access and a pnpm toolchain on every runner; GOAL §3 grants fixture-content freedom while §7 requires the real CLI, which is fully exercised. The commands in the evidence transcript are real commands with real exit codes.
- **Evidence:** `scenarios/uc1/fixture/install.js`; transcript artifacts under `scenarios/uc1/out/artifacts/`.

## m6

### DEC-030: T4 policy self-edit is caught at the schema layer (still I1)
- **What:** T4a proposes a ChangeSet targeting `.loop/policy.yaml`. It is refused with a schema-level message (the `target_path` pattern rejects `.loop/`, DEC-003), before the executor's protected-list I1 message runs.
- **Why:** Defense in depth: I1 is enforced at BOTH the schema and the executor. The schema fires first, so the visible reason cites the `.loop` pattern rather than the literal string "I1". The security property — the loop cannot edit its own policy — holds. The test accepts either attribution.
- **Evidence:** `adversarial/t4.sh`; `docs/DECISIONS.md` DEC-003.

### DEC-031: adversarial tests assert on real file-plane + journal outcomes, never on mocks
- **What:** Every adversarial test drives the real CLI as a subprocess, then asserts on the working tree (poisoned/backdoor file absent), the journal event sequence, and CLI exit codes. The control applies a real change.
- **Why:** GOAL §3 forbidden move 3 (no mocking/import-around in adversarial tests) and §10 (no assertions on mocked core behavior).
- **Evidence:** `adversarial/*.sh`; `adversarial/lib.sh` helpers; `experiments/adversarial/logs/`.

## m7

### DEC-032: raw run logs are gitignored; only aggregated results are committed
- **What:** `experiments/*/logs/` and `scenarios/*/out/` are gitignored. The committed artifacts are `experiments/results/metrics.json` and `paper/figures/*.tex`, both regenerated by `make reproduce`.
- **Why:** Every run appends a new timestamped file, so committing them would grow the repo without adding information — and a stale committed log could contradict a fresh run. `make reproduce` clears logs first, so results always come from the current run (GOAL §10: no metric without a run ID; the run ID lives in `metrics.json`).
- **Evidence:** `.gitignore`; `experiments/reproduce.sh`; `docs/REPRODUCE.md`.

### DEC-033: the trigger experiment is opt-in and excluded from `make verify`
- **What:** `make verify` (the final CI gate) runs offline. The live-model trigger experiment runs only via `make reproduce REPRODUCE_ARGS="--with-trigger"` or directly.
- **Why:** GOAL's final gate demands a fresh CI clone go green; CI has no API credentials, and a gate that depends on a paid external service is not a gate. GOAL B1 marks the trigger rate REPORTED (soft floor), while the hook-denial test and the happy path are HARD gates — both are covered deterministically in `make verify` (`tests/test_hook.py`, conformance c02, `make demo`).
- **Evidence:** `Makefile`; `.github/workflows/ci.yml`; `experiments/reproduce.sh`.

### DEC-034: headless trigger runs need a pre-trusted, pre-allowlisted fixture
- **What:** `run_trigger.py` writes `hasTrustDialogAccepted` for the temp fixture in `~/.claude.json` and pre-allows `Bash(agentloop:*)` in the fixture's `.claude/settings.json`.
- **Why:** Measured behaviour during development: without trust, Claude Code ignores the workspace's `permissions.allow` entries; without the allowlist, a headless session cannot answer approval prompts, so it describes the loop steps instead of running them. Both are environment artifacts of headless mode, not properties of the skill — leaving them in place would have measured the sandbox, not the trigger. The PreToolUse guard still fires, so managed-file protection is unchanged.
- **Evidence:** `experiments/trigger/run_trigger.py`; captured stderr from the failing runs ("this workspace has not been trusted"); `docs/REPRODUCE.md`.

### DEC-035: quota/limit runs are excluded from the trigger denominator, never silently
- **What:** A run whose output matches a session/usage/rate-limit marker is recorded with `error: quota-or-limit` and excluded from `n_valid`. `metrics.py` then reports the rate over valid runs, or prints the reason when none exist.
- **Why:** GOAL forbidden move 4 (no hand-written numbers) and §10 (no metric without a run ID). An environment failure must never be counted as a non-trigger, and must never be quietly dropped either — the paper prints the reason.
- **Evidence:** `experiments/trigger/run_trigger.py`; `experiments/metrics.py`; paper §Limitations.

### DEC-036: the paper's anti-hardcode guard runs in the build
- **What:** `paper/check_no_hardcoded.py` scans the TeX prose for metric-shaped literals and fails `make paper` if one appears. Layout lengths, package options, standard/RFC/article numbers, and years are allow-listed.
- **Why:** GOAL E3 requires that grep prove no hard-coded metric values in the TeX source. Making it a build step rather than a manual grep means the property cannot silently rot.
- **Evidence:** `paper/build.sh` step 2; the guard caught three false positives on first run (geometry margin, Python version, itemize length), which were allow-listed by category rather than by line.

### DEC-037: citations verified against live sources before the paper build
- **What:** All 20 references were checked against arXiv, DOIs, the RFC Editor, EUR-Lex, and official project sites on 2026-08-31. The record is `paper/CITATIONS.md`; the `[VERIFY]` list is empty.
- **Why:** GOAL forbidden move 5. The DGM eval-gaming claim in §1 carries the most argumentative weight, so it was verified specifically: the paper documents a variant scoring perfectly by removing the harness's own hallucination-detection markers.
- **Evidence:** `paper/CITATIONS.md`; `paper/figures/references.tex`.

### DEC-038: `supersedes` exposed on the CLI and SDK
- **What:** `agentloop propose --supersedes <cs-id>` (and the SDK's `supersedes=` argument) now set the envelope field.
- **Why:** The ChangeSet schema has carried `supersedes` since m1, but nothing could set it — found while dogfooding, when a rolled-back lesson was replaced by a corrected one and the replacement could not record what it replaced. A spec field with no way to populate it is a dead field.
- **Evidence:** `src/agentloop/cli.py`, `src/agentloop/changeset.py`, `sdk/loop/__init__.py`; `tests/test_executor.py::test_propose_records_supersedes`.

### DEC-039: no conditional skips in the test suite
- **What:** `tests/test_sdk.py` previously used `pytest.importorskip("loop")`; it now imports directly.
- **Why:** GOAL §3 requires zero skipped tests at final verify. `make setup` always installs the SDK, so an import failure is a real defect; a conditional skip would have hidden it silently on a broken install.
- **Evidence:** `tests/test_sdk.py`; final pytest run reports no skips.
