# GOAL.md — Build, Battle-Test, and Package the Loop Standard v1

**Audience:** Claude Code (autonomous run). **Owner:** Minhal. **Companion file:** `design-doc.md` (normative design — architecture, objects, schema sketches, invariants I1–I6, threats T1–T6, profiles). Read it first. Where this file and `design-doc.md` conflict, this file wins on process, `design-doc.md` wins on protocol semantics.

## 1. Mission

Take the Loop standard from design to a published-quality v1: a working reference implementation, a normative spec, a conformance suite, five executed battle-test scenarios, an adversarial security suite, and a reproducible research paper draft. The end state is one repository that a stranger can clone, verify with one command, and extend — and a paper whose every number regenerates from logged runs.

**The prize sentence you build toward:** "An agent on runtime A learned a lesson at 09:00. By 09:10, an independent runtime B ran with that lesson, because the lesson traveled as a signed ChangeSet, carried evidence, passed policy, entered the journal, and shipped through the registry — and an auditor reconstructed all of it from the journal alone."

## 2. Fixed decisions (do not re-open)

| # | Decision |
|---|---|
| F1 | Language: **Python 3.11+** for CLI, SDK, and conformance driver. TypeScript SDK is a stretch goal only |
| F2 | Working name: **agentloop**. CLI binary: `agentloop` with alias `loop`. Do not brand further; final naming is Minhal's pre-publication step |
| F3 | Licenses: code **Apache-2.0**; spec text **Community Specification License 1.0**. Include both files |
| F4 | Scope: **Core profile complete. Team profile lite** = git-remote registry + detached **ed25519** signatures (minisign-style). **Governed profile: specified in the spec, NOT implemented** — mark clearly |
| F5 | Protocol semantics: the five objects, file plane, lifecycle, trust levels, invariants, and profile table in `design-doc.md` Sections 4–7 and 9 are **normative**. Field names may be refined; semantics may not |
| F6 | Weight updates: journal-only opaque entries, per design decision D2 |
| F7 | Style: all prose (spec, README, paper) follows ASD-STE100 principles — short sentences, active voice, MUST/MUST NOT per RFC 2119 |

## 3. Creative space and guardrails

**You choose freely:** internal code architecture, module layout, test framework, storage details behind the normative file plane, CLI ergonomics beyond the named verbs, scenario fixture content, paper figures, and any extra feature — provided every gate in Sections 5, 10 still passes unchanged.

**Deviation rule:** if you find a better design than `design-doc.md` prescribes, you MAY implement it. You MUST record each deviation in `DECISIONS.md`: what changed, why, what evidence supports it. Silent deviation from normative semantics is a defect.

**Forbidden moves (hard rules):**
1. Do not skip, mute, `xfail`, or delete a failing test to pass a gate. Zero skipped tests at final verify.
2. Do not weaken, remove, or reinterpret a DoD gate. If a gate looks wrong or impossible, STOP: write `BLOCKERS.md` with the problem and your proposal, and ask Minhal.
3. Do not mock or import-around the CLI in scenario and adversarial tests. Scenarios MUST drive the real binary as a subprocess.
4. Do not hand-write any number in the paper. Every quantitative value MUST be generated from run logs by script.
5. Do not fabricate citations. Verify each reference against a live source, or mark it `[VERIFY]` in a visible list. `[VERIFY]` items block paper submission, not repo completion.
6. Do not commit with hooks disabled, and do not edit `.loop/**` by hand after the dogfood milestone (M4).
7. Do not present the demo as passing unless it ran end to end in the current workspace during this run.

**Self-application rule:** the DGM result in `design-doc.md` shows why self-graded success is worthless. Apply that to yourself. A milestone is done when its gate command exits 0 on a fresh state — not when you believe the work is good.

## 4. Target repository layout

```
agentloop/
  spec/            # the normative spec (14 sections per design-doc §10) + schemas/
  src/agentloop/   # CLI + library (the reference Executor)
  sdk/             # Python SDK (five verbs) + toy custom agent
  skill/           # the drop-in Claude Code skill (SKILL.md + scripts/)
  conformance/     # golden-file suite + driver interface for ANY executor
  scenarios/       # UC1–UC5: fixture/ + run.sh + asserts + out/ artifacts
  adversarial/     # threat tests T1, T2, T4, T5, T6
  experiments/     # runner, raw JSONL logs, metrics scripts
  paper/           # LaTeX source, figures/ (generated), built PDF
  demo/            # "one lesson, two runtimes" script
  docs/            # README, QUICKSTART, REPRODUCE, DECISIONS, STATUS
  .loop/           # the repo's own loop (dogfood, from M4)
  .github/workflows/ci.yml
  Makefile         # setup, verify, scenarios, adversarial, reproduce, paper, quickstart-test, demo
```

## 5. Milestones and exit gates

Work in this order. Each gate is a command that MUST exit 0 before the next milestone starts. Tag each milestone in git (`m1`, `m2`, …). Update `docs/STATUS.md` at each tag.

| Tag | Milestone | Exit gate |
|---|---|---|
| m1 | Spec v0.1 text + five JSON Schemas + schema validator + conformance suite skeleton (golden files incl. required-failure cases) | `make check-schemas` — validates all golden files; required-invalid files MUST fail validation |
| m2 | Reference Executor: `agentloop init, propose, evidence, gate, apply, rollback, log, verify` + hash-chained journal | `make conformance` — full suite green against the CLI via the driver |
| m3 | Two doors: drop-in skill, AGENTS.md managed block, SDK five verbs, toy SDK agent, interop demo | `make demo` — one lesson crosses two runtimes; asserts final state + journal |
| m4 | Team-lite: `sync` over a git remote, ed25519 signing, verify-on-pull. **Dogfood starts:** repo's managed files governed by its own `.loop/` from this tag | `make scenarios` (UC1–UC3 subset) + `agentloop verify .` green in CI |
| m5 | Battle tests complete: UC1–UC5 scripted, repeatable, artifacts captured | `make scenarios` — all five green, artifacts regenerated |
| m6 | Adversarial suite: executed attacks for T1, T2, T4, T5, T6, each detected/blocked | `make adversarial` — every attack test passes BY being stopped |
| m7 | Experiments + paper + publication hygiene | `make reproduce && make paper && make verify` green in a fresh clone via CI |

**The final gate (non-negotiable):** on a clean CI runner, `git clone` → `make setup` → `make verify` exits 0. `make verify` MUST run: schema checks, unit tests, conformance, all scenarios, the adversarial suite, `agentloop verify` on the repo's own journal, the quickstart doc-test, and lint. CI config is part of the deliverable and MUST be green on the default branch.

## 6. Epics and user stories

Format: story → acceptance (Given/When/Then, compressed) → verification. Every verification is a command or an artifact path. "Reviewer" is a distinct actor identity used in tests (see Section 11).

### Epic A — Core Executor and file plane

- **A1. Init.** As a product user, I run one command and get a governed workspace. — *Given* an empty repo, *when* `agentloop init`, *then* `.loop/` exists with default policy (context L2, capability L1, architecture L1), an empty journal with a genesis entry, and printed next steps. Verify: unit test + `scenarios/uc1`.
- **A2. Propose + validate.** As a producer, my ChangeSet is schema-checked and allowlist-checked before anything else. — Out-of-allowlist target → VALIDATED fails with a clear error; journal records the rejection. Verify: conformance golden files (valid + required-invalid).
- **A3. Gate + apply at L2.** As an operator, low-risk context changes apply automatically only with independent evidence. — Change with only `grader: self` evidence at L2 → NOT applied (invariant I3); with an independent `command-transcript` → applied, snapshotted, journaled, committed. Verify: conformance + `adversarial/t1`.
- **A4. L1 queue.** As a reviewer, capability changes wait for me. — Proposed capability change → state QUEUED, target untouched; `agentloop approve <id>` as reviewer → applied; `agentloop reject <id>` → never applied, journaled. Both paths tested. Verify: conformance + `scenarios/uc2`.
- **A5. Rollback + de-escalation.** As an operator, one command restores the previous state, and repeated failure lowers autonomy. — After apply, `agentloop rollback <id>` restores exact prior content hashes; two rollbacks in the policy window drop the class one level, journaled as `policy-effective` change. Verify: `scenarios/uc4`.
- **A6. Journal integrity.** As an auditor, tampering is detectable. — Any edit to a past journal line → `agentloop verify` fails and names the break point. Verify: `adversarial/t6`.

### Epic B — Two doors

- **B1. Drop-in skill (consumer door).** As a Claude Code user, the agent proposes instead of editing managed files directly. — Skill per `design-doc.md` §8.1 (assertive description; deterministic steps call the CLI from `scripts/`). A `PreToolUse` hook denies direct edits to policy-managed targets with a message pointing to `agentloop propose`. **Verify Claude Code hook and skill mechanics against live docs (docs.claude.com) before building; record the verified API in `DECISIONS.md`.** Trigger reliability: run ≥5 headless `claude -p` lesson prompts against a fixture repo; REPORT the propose-rate (soft floor 70%); the hook-denial test and one full happy path are HARD gates. Verify: `scenarios/uc1` + `experiments/trigger/`.
- **B2. AGENTS.md door.** As a Codex-class user, `agentloop init` appends a managed contract block to `AGENTS.md`, idempotently. Verify: unit test (double-init produces one block).
- **B3. SDK (creator door).** As a builder, I embed the loop with five verbs. — `Loop(".loop")`, `propose`, `attach_evidence`, `gate`, `apply`, `rollback` (+ `log`, `sync`). A toy custom agent (~200 lines) in `sdk/examples/` uses them end to end. Verify: SDK tests + demo.
- **B4. Interop demo.** As the standard, I prove "one lesson, two runtimes." — `make demo`: a scripted producer session creates a ChangeSet in fixture repo A; the toy SDK agent syncs, gates against its own policy, applies to its own prompt file; assertions check both end states and both journals; wall-clock lesson-to-second-runtime time is logged. Verify: `make demo` + `experiments/interop/`.

### Epic C — Team-lite

- **C1. Registry over a git remote.** As an org, accepted ChangeSets travel through a plain git remote; local gates still decide. — `agentloop sync` pushes promoted ChangeSets and pulls peers'; a pulled ChangeSet NEVER bypasses local policy. Verify: `scenarios/uc3`.
- **C2. Signing.** As a consumer of shared changes, I reject unsigned or bad-signature ChangeSets. — ed25519 detached signatures; tampered payload → sync-verify fails. Verify: `adversarial/t3-lite` (documented as Team-lite, not full Sigstore).

### Epic D — Spec and conformance

- **D1. Spec v0.1.** The 14-section spec per `design-doc.md` §10, RFC 2119 language, Governed sections marked "specified, not implemented in v1." Verify: `spec/` complete; schema section matches `spec/schemas/` byte-for-byte where quoted.
- **D2. Conformance suite as a product.** Golden inputs + expected journals + REQUIRED-FAILURE cases, runnable against ANY executor through a small driver interface (subprocess contract). The reference CLI passes; a deliberately broken executor stub fails. Verify: `make conformance` + the broken-stub negative test.

### Epic E — Research paper

- **E1. Experiments framework.** Every scenario and demo emits JSONL logs with run IDs, versions, seeds, timings. `make reproduce` re-runs all experiments and regenerates every table and figure.
- **E2. Metrics.** Report at minimum: lesson-to-second-runtime time (B4); fleet propagation time (UC3); % of managed-file changes carrying evidence under the loop vs. a no-loop baseline session; adversarial detection outcomes (5/5 expected); skill trigger rate (B1); loop overhead — added wall time and added tokens per session on ≥5 fixed tasks with/without the loop.
- **E3. Paper draft.** LaTeX, 6–10 pages: abstract; problem (design-doc §1); related work (research brief; every citation verified or `[VERIFY]`-listed); design (objects, invariants, trust levels); implementation; evaluation (E2 metrics + scenario narratives); threats and adversarial results; **limitations** (mandatory and honest: Team-lite, Governed unimplemented, single-model trigger data, small n); future work. Every number carries a run-ID footnote. Verify: `make paper` builds the PDF from generated tables; grep proves no hard-coded metric values in the TeX source.

## 7. Battle-test scenarios (the "confirmed loop")

Each scenario = `scenarios/<id>/` with `fixture/` (a small but real project), `run.sh` (drives the real CLI and scripted producer steps), assertions, and captured `out/` artifacts (journal copy, transcripts, timings). All run headless under `make scenarios`.

| ID | Scenario | Must show |
|---|---|---|
| UC1 | **Context lesson.** Fixture repo where `npm install` fails and `pnpm install` works. Producer learns it, proposes an `AGENTS.md` diff with a fail→apply→pass command transcript | L2 auto-apply with independent evidence; next session benefits; journal complete |
| UC2 | **Capability repair.** A bundled skill has a broken script; producer proposes the fix | L1 queue honored (no apply before approval); reviewer approve path AND a reject path both exercised |
| UC3 | **Fleet propagation.** Workspaces A and B share a git-remote registry; lesson lands in A | B receives it via `sync`, gates locally, applies; propagation time logged; a policy-violating pulled change is refused in B |
| UC4 | **Regression + ratchet-down.** An applied change breaks a real test in the observation window | Detection, one-command rollback to exact prior hashes, de-escalation triggers and is journaled |
| UC5 | **Audit reconstruction.** After UC1–UC4, a script answers "why does this workspace behave this way today?" | The explanation is generated from the journal ALONE (no git log, no source diffs) and matches reality |

## 8. Adversarial suite (executed attacks)

Each test performs the attack for real and passes only if the system stops or detects it. Map: **T1** self-graded evidence pushed at L2 → refused (I3). **T2** injected instruction in fixture content drives a proposal targeting a non-allowlisted memory path → validation refuses (I4); the attempt is journaled. **T4** ChangeSet targeting `.loop/policy.yaml` → invalid (I1); direct hand-edit after m4 → CI `agentloop verify` fails. **T5** hostile fixture webpage/file induces a plausible-looking capability backdoor proposal → it lands in the L1 queue, never auto-applies; the diff+rationale surface for review. **T6** journal line tampered → verification fails at the exact entry. Include one **control**: a legitimate change passes through untouched, proving the gates are not theater that blocks everything.

## 9. Global Definition of Done (v1)

1. Fresh-clone CI gate green (Section 5 final gate).
2. Conformance: reference CLI passes; broken-stub fails; every required-failure golden case fails correctly.
3. All five scenarios green with regenerated artifacts; all five adversarial tests green; the control passes.
4. `make demo` green; interop time logged.
5. Dogfood: from tag m4, every change to this repo's managed files has a valid journal entry; at least one REAL rollback exists in the repo's own journal; `agentloop verify .` green in CI.
6. Zero skipped/xfail tests; scenario+adversarial layers use the real binary only.
7. Spec v0.1 complete; schemas normative; Governed marked unimplemented.
8. Docs: README with the 10-minute consumer path (doc-tested via `make quickstart-test`), QUICKSTART, REPRODUCE, DECISIONS, STATUS, BLOCKERS (may be empty), LICENSE files per F3.
9. `make reproduce && make paper` regenerate all numbers, tables, figures, and the PDF; `[VERIFY]` citation list present if non-empty.
10. `docs/STATUS.md` final entry: gate-by-gate self-report with the exact commands and their exit codes.

## 10. Definition of NOT done (reject your own work if…)

Any gate passes only in a dirty workspace; any metric exists without a run ID; any test asserts on mocked core behavior; the demo narrative and the demo script differ; the paper claims "battle-tested" beyond what Sections 7–8 actually executed; the limitations section is missing or cosmetic.

## 11. Human interaction protocol

- Milestone tags m1–m7 are Minhal's review points. Continue autonomously between tags; STOP and ask only via `BLOCKERS.md` when a gate is impossible or a normative conflict appears.
- In tests and scenarios, L1 approvals are issued by a distinct **reviewer actor identity** recorded in the journal — never by the producer identity in the same flow. This tests the mechanism; it does not simulate wisdom.
- For THIS repo's own loop (dogfood), Minhal is the only L1 approver of capability/architecture changes. Queue and proceed with other work; never self-approve.
- Minhal personally owns: the final protocol name and rename, the public GitHub push, license confirmation, and paper submission. Prepare everything; execute nothing public.

## 12. Final report

At m7, write `docs/STATUS.md` §Final: what was built, every gate with its command and exit code, all E2 metrics with run IDs, the DECISIONS.md summary, the open `[VERIFY]` list, and the exact remaining human steps to publish. One page. STE style.
