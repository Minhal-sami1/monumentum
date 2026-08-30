# The Loop Standard — Specification v0.1

**Status:** Draft v0.1
**Spec tag:** `loop/v0.1`
**License:** Community Specification License 1.0 (see `LICENSE-SPEC.md`)
**Normative schemas:** `spec/schemas/` (Section 13)

This document uses ASD-STE100 principles: short sentences, active voice, one idea per sentence.

---

## 1. Introduction and problem statement

Agent experience does not compound. Every deployed agent learns during work. Then one of two bad things happens. Path one: the context ends, and the lesson dies. Path two: the lesson persists as a memory write, a prompt edit, or a saved skill — with no evidence, no gate, no audit trail, and no way to reach any other agent.

This standard supplies the missing infrastructure for the improvement loop: a unit of improvement, a proof, a brake, a record, and a distribution channel. It does not make models smarter. It makes a change **proven, gated, recorded, reversible, and portable**.

The standard governs three change layers:

| Layer | What changes | Example targets |
|---|---|---|
| context | Instructions, memory, few-shot content | `AGENTS.md`, `CLAUDE.md`, memory files |
| capability | Executable skills and tool code | `.claude/skills/**`, `tools/**` |
| architecture | The agent graph and its policies | orchestration config, routing rules |

Model weights are out of scope for v0.1. A weight update is recordable only as an opaque Journal entry (Section 8.4).

## 2. Terminology and conformance language

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described in RFC 2119.

- **Workspace.** A directory tree that contains agent-steering files and one `.loop/` directory.
- **ChangeSet.** The unit of improvement: a typed, portable record of one self-modification (Section 5).
- **Evidence.** A record that supports one ChangeSet (Section 6).
- **Policy.** The declared change envelope of a workspace (Section 7).
- **Journal.** The append-only, hash-chained event log of a workspace (Section 8).
- **Registry.** An org-scoped distribution channel for accepted ChangeSets (Section 10).
- **Target.** A workspace-relative file path that a ChangeSet modifies.
- **Gate.** A deterministic check that the Executor evaluates before apply.
- **Trust level.** One of L0–L3 (Section 7.2).

## 3. Conformance: roles and profiles

### 3.1 Roles

- **Producer.** Any component that emits a valid ChangeSet with evidence. A Producer MAY be a model, an optimizer, or a human with a CLI.
- **Executor.** The component that validates, gates, applies, journals, and rolls back changes. An Executor MUST be deterministic code. A model MUST NOT be the gatekeeper of its own change.
- **Distributor.** A registry that serves accepted ChangeSets across an organization. Team profile and above.

Any conformant Producer works with any conformant Executor. That sentence is the interoperability claim of this standard.

### 3.2 Profiles

| Requirement | Core | Team | Governed |
|---|---|---|---|
| File plane, five objects, lifecycle | MUST | MUST | MUST |
| Journal hash chain + rollback | MUST | MUST | MUST |
| Evidence on every applied change | MUST | MUST | MUST |
| Independent evidence for L2+ | MUST | MUST | MUST |
| Signed ChangeSets + provenance | — | MUST | MUST |
| Registry (Distributor role) | — | MUST | MUST |
| Transparency-log Journal, signed entries | — | — | MUST |
| Policy in a policy language (Rego/OPA) | — | — | MUST |
| Retention and export for audit | — | — | MUST |

**Governed profile status: specified, NOT implemented in v1.** Sections that apply only to Governed are marked. A v1 implementation MUST NOT claim Governed conformance.

**Team profile in v1 ("Team-lite"):** the reference implementation provides a git-remote Registry and detached ed25519 signatures. Full Sigstore signing and in-toto provenance are specified for Team but the v1 reference implements the lite subset. An implementation that provides only Team-lite MUST say so.

## 4. The file plane

The Core representation is a directory of plain files. No server. No daemon.

```
.loop/
  policy.yaml            # the declared change envelope (Section 7)
  journal/
    <YYYY-MM>.ndjson     # append-only, hash-chained entries (Section 8)
  changesets/
    <changeset-id>/
      changeset.json     # the ChangeSet envelope (Section 5)
      payload.patch      # payload artifact (diff payloads)
      payload/           # payload artifact (folder payloads)
      evidence/
        <evidence-id>.json
        <artifact files>
  state.json             # executor-managed: applied set, current heads
  registry.yaml          # Team profile only (Section 10)
```

Rules:

1. `.loop/**` MUST NOT be a valid change target (invariant I1).
2. Targets MUST live under version control, or the Executor MUST snapshot them before apply.
3. Journal entries MUST reference content hashes. They SHOULD reference git commits when present.
4. All paths inside ChangeSets MUST be POSIX-style relative paths. Absolute paths, `..` segments, backslashes, and drive letters are invalid.

## 5. ChangeSet

The unit of improvement. Normative schema: `spec/schemas/changeset.schema.json`.

A ChangeSet is one JSON object in `changeset.json` inside its own folder under `.loop/changesets/`. Required fields: `spec`, `id`, `layer`, `targets`, `payload`, `origin`, `rationale`, `evidence`, `created`.

- `spec` MUST equal `loop/v0.1`.
- `id` MUST match `cs-<YYYYMMDD>-<suffix>` per the schema pattern. Ids MUST be unique within a workspace.
- `layer` MUST be one of `context`, `capability`, `architecture`.
- `targets` MUST list at least one workspace-relative path. Every target MUST satisfy the path rules of Section 4.
- `payload.type` MUST be one of:
  - `diff` — a unified diff against the target files. `path` and `sha256` are REQUIRED.
  - `folder` — a folder that replaces or creates the targets. `path` and `sha256` are REQUIRED. The hash covers a deterministic archive of the folder content.
  - `opaque` — an external payload (Section 8.4). `ref` is REQUIRED. The Executor MUST NOT apply an opaque payload; it only journals the event.
- `rationale` MUST NOT be empty.
- `evidence` lists Evidence record paths relative to the ChangeSet folder. It MAY be empty at PROPOSED. Gates enforce evidence before APPLIED (Section 9).
- `provenance` is `null` in Core. In Team it SHOULD carry an in-toto attestation. Team-lite implementations MAY leave it `null` and sign the ChangeSet folder instead (Section 10.3).
- `supersedes` names an earlier ChangeSet id or is `null`.
- Non-standard fields MUST go inside `ext`. The root object is closed.

## 6. Evidence

Normative schema: `spec/schemas/evidence.schema.json`.

An Evidence record is one JSON object. Required fields: `id`, `kind`, `grader`, `format`, `summary`.

- `kind` MUST be one of `eval`, `telemetry`, `human`, `reproduction`.
- `grader` MUST be `self` or `independent`. An `independent` grader is a held-out check, a separate grader model, a CI run, or a human — never the producing model grading its own output in the same flow.
- `format` MUST be one of:
  - `inspect-log` — UK AISI Inspect result log.
  - `lm-eval` — EleutherAI evaluation harness result.
  - `otel-genai` — OpenTelemetry GenAI spans.
  - `human-feedback` — recorded human judgment.
  - `command-transcript` — the cheap Core format: run the failing command, apply the change, run it again, attach the transcript.
- `artifact` (path + sha256) is REQUIRED for every format except `human-feedback`, where it is OPTIONAL.
- `summary.metric` MUST name what was measured. `before`, `after`, and `n` SHOULD be present for eval evidence.

Evidence rules:

1. No change applies without evidence. An Executor MUST refuse to apply a ChangeSet whose effective evidence list is empty.
2. **Invariant I3:** application at L2 or L3 REQUIRES at least one Evidence record with `grader: independent`. Self-graded evidence alone is never sufficient above L1.
3. The Executor MUST verify each `artifact.sha256` against the artifact file before it counts the record.

## 7. Policy and trust levels

Normative schema: `spec/schemas/policy.schema.json`. The Policy lives at `.loop/policy.yaml`.

### 7.1 Structure

The Policy declares, per change class: a trust `level`, a list of `gates`, and a `targets_allow` list of glob patterns. It also declares `protected` patterns, optional `escalation` and `de_escalation` rules, and `audit` settings.

- `protected` MUST contain `.loop/**` (invariant I1).
- **Invariant I4:** a ChangeSet whose target matches no `targets_allow` pattern of its class, or matches any `protected` pattern, MUST fail validation.
- Only a human MAY change `policy.yaml`. A policy change is an architecture-class, L1 event, and the Executor MUST journal it as `policy_changed`.

### 7.2 Trust levels

| Level | Meaning | Human role |
|---|---|---|
| L0 | Suggest only. Nothing applies | Reads suggestions |
| L1 | Each change queues for approval | Approves each change |
| L2 | Automatic gates apply the change | Audits after the fact |
| L3 | Full autonomy inside the envelope | Sets policy; reviews journal |

Defaults: context = L2, capability = L1, architecture = L1. Rollback and the Journal are mandatory at every level, including L0: proposals are journaled too.

### 7.3 Core gates

Core defines three built-in deterministic gates:

- `evidence_required` — the effective evidence list is non-empty and every artifact hash verifies.
- `reproducible_check` — for `command-transcript` evidence, the Executor re-runs the recorded check command and REQUIRES the recorded outcome. For other formats, the Executor verifies artifact integrity.
- `human_review` — the ChangeSet queues. A distinct reviewer actor MUST approve before apply. The producer identity MUST NOT approve its own ChangeSet in the same flow.

Gate evaluation MUST be deterministic code. Governed MAY express gates in Rego/OPA (specified, not implemented in v1).

### 7.4 Escalation and de-escalation

- `escalation` MAY raise a class one level after a recorded track record: at least `after.applied` applied changes, at most `after.rollbacks_max` rollbacks, inside `after.window_days`.
- `de_escalation` MUST lower the class level by `drop` when `on_rollbacks` rollbacks occur inside `window_days`. The ratchet also turns down.
- Both transitions are policy-effective changes. The Executor MUST journal them as `policy_changed` with the trigger in `decision.reason`. The declared file `policy.yaml` stays human-owned; the Executor records the effective level in `state.json`.

## 8. Journal

Normative schema (one entry): `spec/schemas/journal-entry.schema.json`.

### 8.1 Format

The Journal is NDJSON: one JSON object per line, UTF-8, `\n` line separator. Files live under `.loop/journal/` named `<YYYY-MM>.ndjson` by entry timestamp. The Journal is append-only.

### 8.2 Hash chain

- Entry `seq` numbers are consecutive integers from 0 across all journal files of a workspace.
- Entry 0 is the **genesis** entry. Its `prev` is `null`. It records the initial policy hash.
- Every later entry's `prev` MUST be `sha256:<hex>` of the exact previous NDJSON line (the serialized bytes without the trailing newline).
- **Invariant I2:** any edit or deletion of a past line breaks verification. A verifier MUST report the first broken sequence number.

### 8.3 Events

`genesis`, `proposed`, `gated`, `approved`, `rejected`, `applied`, `observed`, `rolled_back`, `promoted`, `shared`, `policy_changed`, `weight_update`.

`rejected` covers both validation failure and gate rejection; `decision.reason` says which. Every entry names its `actor`: `executor/<name>@<version>`, `producer/<id>`, `reviewer/<id>`, or `human/<id>`.

### 8.4 Opaque weight updates

A weight update is recorded as one `weight_update` entry whose `ext.weight_update` names the before version, the after version, and the external payload reference. The Executor MUST NOT fetch or apply the payload. Evidence MAY be attached through a ChangeSet with `payload.type: opaque`.

### 8.5 The audit promise

An auditor MUST be able to reconstruct, from the Journal alone, why any workspace behaves the way it behaves today: which changes applied, under which policy, with which evidence, approved by whom, and which rolled back.

## 9. Lifecycle

```
PROPOSED → VALIDATED → GATED → APPLIED → OBSERVED → PROMOTED
                │          │        │         │
                └─ REJECTED┘        └──── ROLLED_BACK ◄──────┘
```

- **PROPOSED.** A Producer writes a ChangeSet folder. The Executor journals `proposed`.
- **VALIDATED.** The Executor checks the schema, the target allowlist (I4), the protected list (I1), and the payload hash. Failure journals `rejected`.
- **GATED.** The Executor evaluates the Policy gates for the class. Results: auto-approve (L2/L3 with gates passed), queue for human (L1, journals `gated` with queue decision), or reject. At L0 nothing applies.
- **APPLIED.** The Executor snapshots the targets, applies the payload, journals `applied` with before/after hashes, and commits when the workspace is a git repository.
- **OBSERVED.** A post-apply window collects telemetry. Journaled as `observed`.
- **ROLLED_BACK.** Allowed from APPLIED, OBSERVED, or PROMOTED at any time. One command. **Invariant I5:** every applied ChangeSet MUST be reversible with one command, restoring the exact prior content hashes.
- **PROMOTED.** The ChangeSet becomes eligible for the Registry.

State transitions MUST be journaled in order. An Executor MUST NOT apply a ChangeSet that did not pass VALIDATED and GATED in this workspace — including ChangeSets pulled from a Registry.

## 10. Registry and distribution (Team profile)

Normative schema: `spec/schemas/registry.schema.json`. Configuration lives at `.loop/registry.yaml`.

### 10.1 Model

The v0.1 Distributor is a plain git remote that holds `changesets/` and the shared journal segment. `kind: git-remote` is the only v0.1 kind. An OCI registry is the specified upgrade path — not implemented in v1.

### 10.2 Sync semantics

- `sync` pushes locally PROMOTED ChangeSets and pulls peers' ChangeSets.
- A pulled ChangeSet enters the local lifecycle at PROPOSED. **Distribution never bypasses gates.** The local Executor MUST validate and gate every pulled ChangeSet against local Policy before apply.

### 10.3 Signing (Team-lite)

- **Invariant I6:** a Distributor serves only signed ChangeSets.
- Team-lite signing: a detached ed25519 signature over a canonical digest of the ChangeSet folder (envelope, payload, evidence). Public keys of trusted producers live in the workspace (`verify.pubkeys_dir`).
- On pull, the Executor MUST verify the signature before validation. Unsigned or bad-signature ChangeSets MUST be refused and journaled as `rejected`.
- Full Team signing is Sigstore plus in-toto provenance: specified, not implemented in v1.

## 11. Security considerations

### 11.1 Invariants (normative)

- **I1 — No self-hosting.** `.loop/**` is never a valid target. Policy changes are human-only, architecture-class, journaled.
- **I2 — Append-only journal.** Entries are hash-chained; deletion or edit breaks verification.
- **I3 — No self-graded promotion.** L2/L3 application requires at least one `independent` evidence record.
- **I4 — Allowlisted targets.** A ChangeSet touching a path outside `targets_allow` fails validation.
- **I5 — Rollback always available.** Every applied ChangeSet is reversible with one command.
- **I6 — Signed distribution.** (Team+) A Distributor serves only signed ChangeSets with provenance.

### 11.2 Threat model

| # | Threat | Mitigation |
|---|---|---|
| T1 | Eval gaming / reward hacking: the producer grades its own change | I3; held-out checks; grader ≠ producer; `reproducible_check` |
| T2 | Memory poisoning, persistent prompt injection | Context writes gated + journaled; I4 allowlists; origin recorded |
| T3 | Malicious skills, supply chain | I6 signing; provenance; local gates never bypassed |
| T4 | Loop self-capture: the agent edits its own policy or journal | I1; I2; `verify` in CI |
| T5 | Injected proposals: hostile content induces a backdoor proposal | L1 human review for capability/architecture; I4; evidence must reproduce; small reviewable diffs |
| T6 | Journal tampering | Hash chain (Core); transparency log + signatures (Governed) |

### 11.3 Enforcement placement

Instruction is not enforcement. A skill or prompt teaches the loop; only deterministic code enforces it. The universal backstop is `verify` in CI: every diff to a managed target MUST have a matching, valid journal entry, and the hash chain MUST be intact. No ungoverned change reaches the main branch — on any harness, with any model.

## 12. Regulatory mapping annex (informative)

This section is informative, not normative. The Policy file is designed to map onto pre-authorized change-control structures:

- **EU AI Act.** Article 12 (record-keeping): the Journal. Article 19 (automatically generated logs): journal retention (`audit.retain_days`). Article 43(4) (substantial modification): the Policy envelope declares pre-approved change classes; changes inside the envelope are recorded and auditable.
- **FDA PCCP (Predetermined Change Control Plan).** The Policy maps one-to-one: (a) allowed change classes = `envelope`, (b) the promotion protocol = gates + lifecycle, (c) the impact boundary = `targets_allow` + `protected`.
- **ISO/IEC 42001.** Change management and logging controls map to the lifecycle and the Journal.
- **NIST AI RMF.** Govern/Map/Measure/Manage: the Policy declares (Govern), evidence measures (Measure), gates and rollback manage (Manage).

A Governed-profile implementation is expected to ship an auditor-facing export. Specified, not implemented in v1.

## 13. Normative JSON Schemas

The five schema files under `spec/schemas/` are normative and are incorporated by reference:

1. `changeset.schema.json`
2. `evidence.schema.json`
3. `policy.schema.json`
4. `journal-entry.schema.json`
5. `registry.schema.json`

All are JSON Schema draft 2020-12. Where this document and a schema disagree, the schema wins for structure and this document wins for behavior. Any excerpt of a schema quoted elsewhere in this repository MUST match the schema file byte-for-byte.

## 14. Conformance test suite

The conformance suite lives in `conformance/`:

- **Schema level (v0.1, milestone m1).** A golden corpus per object type. Files under `valid/` MUST validate. Files under `invalid/` are REQUIRED-FAILURE cases and MUST fail validation. A conformant validator reproduces both outcomes exactly.
- **Executor level (milestone m2).** Golden cases drive ANY executor through a subprocess contract: known ChangeSets in, expected journal out. The reference CLI passes; a deliberately broken executor stub fails. An Executor claims conformance only by passing this suite.

---

## Appendix A: harness integration notes (informative)

**Claude Code.** The drop-in package is a skill plus hooks plus the CLI. The skill carries the cognition: when you learn a durable lesson, propose — never edit managed targets directly. A `PreToolUse` hook denies direct edits to policy-managed targets and points to `agentloop propose`. The CLI carries the enforcement. Hook and skill mechanics are verified against current documentation during implementation (see `docs/DECISIONS.md`).

**AGENTS.md harnesses (Codex-class).** `agentloop init` appends a managed contract block to `AGENTS.md`, idempotently. These harnesses may lack hooks; enforcement rests on the CLI plus `verify` in CI.

## Appendix B: producer adapter guide (informative)

An optimizer becomes a Producer with a thin exporter that emits its output as a ChangeSet:

- **DSPy:** emit the compiled-program JSON as a context-layer ChangeSet with eval evidence.
- **GEPA:** emit the evolved prompt as a diff with trace-based evidence.
- **Memory systems:** emit consolidation writes as gated context changes.

The adapter contract: write the ChangeSet folder per Section 5, attach evidence per Section 6, and let the local Executor gate it. The standard does not compete with optimizers. It makes their outputs portable, comparable, and governable.
