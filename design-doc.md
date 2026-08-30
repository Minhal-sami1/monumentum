# Design Document — Open Standard for Governed Agent Self-Improvement

**Status:** Draft v0.1 for review · **Editor:** Minhal · **Date:** 2026-08-30
**Working name:** "the Loop standard" (final name: Section 13). Examples use `.loop/` as the directory name.
**Style note:** This document uses ASD-STE100 principles: short sentences, active voice, one idea per sentence.

---

## 1. Problem statement

Agent experience does not compound. Every deployed agent learns during work. Then one of two bad things happens. Path one: the context ends, and the lesson dies. Path two: the lesson persists as a memory write, a prompt edit, or a saved skill — with no evidence, no gate, no audit trail, and no way to reach any other agent. Agents forget what they should keep, and keep what nobody checked.

This standard supplies the missing infrastructure for the fast improvement loop: a unit of improvement, a proof, a brake, a record, and a distribution channel. It does not make models smarter. It makes a change **proven, gated, recorded, reversible, and portable**.

## 2. Scope, locked decisions, and non-goals

| # | Decision | Value |
|---|---|---|
| D1 | Change surface | Three layers: **context** (prompts, memory), **capability** (skills, tool code), **architecture** (agent graph, policies) |
| D2 | Model weights | Out of v1. Weight updates are recordable as opaque Journal entries only |
| D3 | Control model | Trust levels **L0–L3** per change class. Audit trail and rollback are mandatory at all levels |
| D4 | Evidence rule | No change applies without attached evidence |
| D5 | Sharing scope v1 | Improvements move between agents **inside one organization**. Public exchange is v2 |
| D6 | First deliverable | Open spec. Then conformance suite. Then thin reference implementation |
| D7 | Profiles | **Core** (one agent, plain files), **Team** (adds registry), **Governed** (full evidence, gates, audit) |
| D8 | Adoption rule (this document) | **One artifact, two doors.** A product user (Claude Code, Codex) adopts in minutes. A custom-agent builder adopts in a day. Both doors lead to the same files |

**Non-goals.** The standard does not define agent-to-agent messaging (A2A does), tool access (MCP does), model training, or the metrics themselves. Adopters select their own metrics; the standard makes the evidence portable.

## 3. Design principles

1. **Files first.** The Core representation is a directory of plain files. No server. No daemon. Any agent that can read and write files can participate. This is the AGENTS.md lesson.
2. **Instruction is not enforcement.** A skill can teach the loop. Only deterministic code may enforce it. The Darwin Gödel Machine gamed its own checks; a model must never be the gatekeeper of its own change.
3. **Govern what already exists.** The change targets are the files that already steer agents: `AGENTS.md`, `CLAUDE.md`, skill folders, memory files, agent config. Adoption requires zero migration.
4. **Reuse formats.** Wrap in-toto/SLSA for provenance, Inspect and lm-eval result schemas for eval evidence, OpenTelemetry GenAI spans for telemetry, hash chains and transparency logs for the Journal, OCI or a git remote for distribution.
5. **Evidence before promotion.** Self-graded evidence is never sufficient above L1.
6. **Small core, strict extensions.** Core must be adoptable in one afternoon. Team and Governed add requirements; they never change Core semantics.
7. **The loop is not self-hosting.** The loop must not modify its own policy or journal. See Invariant I1.

## 4. Architecture

### 4.1 Three change layers

| Layer | What changes | Example targets |
|---|---|---|
| Context | Instructions, memory, few-shot content | `AGENTS.md`, `CLAUDE.md`, memory files, optimized prompts |
| Capability | Executable skills and tool code | `.claude/skills/**`, `tools/**`, MCP server config |
| Architecture | The agent graph and its policies | orchestration config, sub-agent definitions, routing rules |

### 4.2 Conformance roles

The spec defines three roles. Roles are orthogonal to profiles.

- **Producer.** Anything that emits a valid ChangeSet with evidence. Examples: a model following the drop-in skill, a DSPy or GEPA exporter, a human using the CLI.
- **Executor.** The component that validates, gates, applies, journals, and rolls back changes. The reference CLI and SDK are executors. An executor must be deterministic code.
- **Distributor.** (Team profile and above.) A registry that serves accepted ChangeSets across an organization.

Any conformant Producer works with any conformant Executor. That sentence is the interoperability claim of the whole standard.

### 4.3 Lifecycle state machine

```
PROPOSED → VALIDATED → GATED → APPLIED → OBSERVED → PROMOTED
                │          │        │         │
                └─ REJECTED┘        └──── ROLLED_BACK ◄──────┘
```

- **PROPOSED:** a Producer writes a ChangeSet folder.
- **VALIDATED:** the Executor checks schema, target allowlist, and payload hash.
- **GATED:** the Executor evaluates Policy. Result: auto-approve (L2/L3), queue for human (L1), or reject.
- **APPLIED:** the Executor snapshots targets, applies the payload, and journals the event.
- **OBSERVED:** a post-apply window collects telemetry.
- **PROMOTED:** the ChangeSet becomes eligible for the Registry (Team).
- **ROLLED_BACK:** allowed from APPLIED, OBSERVED, or PROMOTED at any time. One command.

### 4.4 The file plane (normative Core representation)

```
.loop/
  policy.yaml            # the declared change envelope (Section 5.3)
  journal/
    2026-08.ndjson       # append-only, hash-chained entries (Section 5.4)
  changesets/
    cs-20260830-a1b2/
      changeset.json     # typed envelope (Section 5.1)
      payload.patch      # unified diff against target files
      evidence/
        ev-001.json      # evidence records (Section 5.2)
  state.json             # executor-managed: applied set, current heads
  registry.yaml          # Team profile only: where to push/pull
```

Rules: `.loop/**` is never a valid change target. Targets must live under version control, or the Executor must snapshot them before apply. Journal entries reference content hashes and, when present, git commits.

## 5. The five objects

### 5.1 ChangeSet

The unit of improvement. A typed, portable record of one self-modification.

```json
{
  "spec": "loop/v0.1",
  "id": "cs-20260830-a1b2",
  "layer": "context",
  "targets": ["AGENTS.md"],
  "payload": { "type": "diff", "path": "payload.patch", "sha256": "…" },
  "origin": { "producer": "claude-code", "model": "…", "session": "…", "trigger": "reflection" },
  "rationale": "Repo uses pnpm. npm install fails on postinstall hooks.",
  "evidence": ["evidence/ev-001.json"],
  "provenance": null,
  "supersedes": null,
  "created": "2026-08-30T09:14:02Z"
}
```

Payload types: `diff` (context, capability, architecture files), `folder` (a whole new skill), `opaque` (D2 weight-update stub: model version A replaced by version B, evidence attached, payload external). Team profile adds `provenance` as an in-toto attestation and a Sigstore signature. The envelope is defined as JSON Schema.

### 5.2 Evidence

```json
{
  "id": "ev-001",
  "kind": "eval",
  "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "task_pass", "before": 0, "after": 1, "n": 3 },
  "artifact": { "path": "ev-001.log", "sha256": "…" }
}
```

- `kind`: `eval` | `telemetry` | `human` | `reproduction`.
- `grader`: `self` | `independent`. **L2 and L3 promotion requires at least one `independent` record** (a held-out check, a separate grader model, a CI run, or a human). This is the direct answer to the DGM eval-gaming result.
- `format` references existing schemas instead of inventing them: `inspect-log` (UK AISI Inspect), `lm-eval` (EleutherAI harness), `otel-genai` (OpenTelemetry GenAI spans), `human-feedback`, and `command-transcript` — the cheap Core-profile format: run the failing command, apply the change, run it again, attach the transcript.

### 5.3 Policy

The machine-readable declared change envelope.

```yaml
spec: loop/v0.1
envelope:
  context:
    level: L2
    gates: [evidence_required, reproducible_check]
    targets_allow: ["AGENTS.md", "CLAUDE.md", ".claude/memory/**"]
  capability:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: [".claude/skills/**", "tools/**"]
  architecture:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: ["agents.yaml"]
protected: [".loop/**"]
escalation:
  capability: { to: L2, after: { applied: 20, rollbacks_max: 1, window_days: 30 } }
de_escalation: { on_rollbacks: 2, window_days: 14, drop: 1 }
audit: { journal: hash-chain, retain_days: 365 }
```

Core evaluates gates with built-in deterministic checks. Governed may express gates in a policy language (Rego/OPA is the candidate). The Policy file maps one-to-one onto the FDA PCCP structure and EU AI Act Article 43(4): (a) allowed change classes, (b) the promotion protocol, (c) the impact boundary. Only a human may change `policy.yaml`; a policy change is itself an architecture-class, L1 event and it is journaled.

### 5.4 Journal

Append-only NDJSON. Each entry carries the SHA-256 of the previous entry (hash chain). Governed upgrades to a Merkle transparency log (Trillian/Rekor design) with signed entries.

```json
{"seq":412,"prev":"sha256:…","ts":"2026-08-30T09:15:00Z","event":"applied",
 "cs":"cs-20260830-a1b2","decision":{"gate":"L2-auto","policy_sha256":"…"},
 "target_state":{"before":"sha256:…","after":"sha256:…","commit":"abc123"},
 "actor":"executor/loop-cli@0.1.0","sig":null}
```

Event types: `proposed`, `gated`, `approved`, `rejected`, `applied`, `observed`, `rolled_back`, `promoted`, `shared`, `policy_changed`, `weight_update` (opaque, per D2). The audit promise: an auditor can reconstruct, from the Journal alone, why any agent behaves the way it behaves today.

### 5.5 Registry (Team profile)

Org-scoped distribution of accepted ChangeSets. Minimum viable Distributor: **a git remote that holds `changesets/` and the shared journal segment.** No new infrastructure. The upgrade path is an OCI registry: ChangeSets as OCI artifacts, Sigstore signatures, existing auth and replication. `loop sync` pulls accepted ChangeSets; the local Executor still gates them against local Policy before apply. Distribution never bypasses gates.

## 6. Trust levels and gates

| Level | Meaning | Human role |
|---|---|---|
| L0 | Suggest only. Nothing applies | Reads suggestions |
| L1 | Each change queues for approval | Approves each change |
| L2 | Automatic gates apply the change | Audits after the fact |
| L3 | Full autonomy inside the envelope | Sets policy; reviews journal |

Defaults per class: context = L2, capability = L1, architecture = L1. Escalation only through a recorded track record (Policy `escalation` block). De-escalation is automatic on rollbacks (`de_escalation` block): the ratchet also turns down. Rollback and the Journal are mandatory at every level, including L0 (proposals are journaled too).

## 7. Conformance profiles

| Requirement | Core | Team | Governed |
|---|---|---|---|
| File plane, five objects, lifecycle | ✔ | ✔ | ✔ |
| Journal hash chain + rollback | ✔ | ✔ | ✔ |
| Evidence on every applied change | ✔ | ✔ | ✔ |
| Independent evidence for L2+ | ✔ | ✔ | ✔ |
| Signed ChangeSets (Sigstore) + in-toto provenance | — | ✔ | ✔ |
| Registry (Distributor role) | — | ✔ | ✔ |
| Transparency-log Journal, signed entries | — | — | ✔ |
| Policy in Rego/OPA, PCCP/Art. 43(4) mapping annex | — | — | ✔ |
| Retention and export for audit | — | — | ✔ |

Core target: adoptable in one afternoon by one person. Governed target: a compliance officer can hand the Journal and Policy to an auditor and map them to EU AI Act Articles 12, 19, and 43(4), to FDA PCCP, and to ISO/IEC 42001 change control.

## 8. Adoption: one artifact, two doors (D8)

### 8.1 The consumer door — Claude Code, Codex, and other harnesses

**The insight that makes this door cheap:** in these products, everything the loop must change is already a file. `AGENTS.md` and `CLAUDE.md` are the context layer. Skill folders are the capability layer. Config files are the architecture layer. The harness already runs commands and tests (evidence) and already sits in git (rollback). So the drop-in package adds only the missing parts: the proposal habit and the enforcement.

**The drop-in package = a skill + a small CLI + hooks.** A skill alone is not enough. A skill is advisory text; principle 2 forbids advisory-only gates. So the package splits the work:

- **The skill carries the cognition.** `SKILL.md` teaches the model: when you learn a durable lesson, when the user corrects you twice, when a flaky task becomes stable — draft a ChangeSet with `loop propose`, attach evidence, and never edit managed targets directly. The skill description must be assertive so it triggers reliably (lessons, corrections, "remember this", end of long sessions). Per the skill format, deterministic scripts ship inside the skill's `scripts/` folder and execute without loading into context.
- **The CLI carries the enforcement.** `loop` validates schemas, checks allowlists, evaluates gates, writes the hash-chained journal, applies with snapshot, and rolls back. The model cannot rewrite it mid-session, and `.loop/**` is protected (I1).
- **Hooks carry the guarantees (Claude Code).** A `PreToolUse` hook denies direct `Edit`/`Write` calls on policy-managed targets and answers: "this file is loop-managed; use `loop propose`." A `Stop`/session-end hook runs `loop status --remind` so unproposed lessons surface before the session closes. Hook and settings mechanics must be verified against current docs (docs.claude.com) during implementation.
- **AGENTS.md harnesses (Codex and others).** `loop init` appends a managed block to `AGENTS.md` with the same behavioral contract. These harnesses may lack hooks, so enforcement rests on the CLI plus the universal backstop below.

**Universal backstop: `loop verify` in CI.** One command checks that every diff to a managed target has a matching, valid journal entry, and that the hash chain is intact. Run it in CI and no ungoverned change reaches the main branch — on any harness, with any model. This makes the guarantee harness-independent.

**Install flow (target: under ten minutes):**

```
npx @loop/cli init
# 1. Scaffolds .loop/ with a default policy (context L2, capability L1, architecture L1)
# 2. Detects .claude/  -> installs the skill into .claude/skills/loop/ and offers hooks
# 3. Detects AGENTS.md -> appends the managed contract block
# 4. Prints the one-line CI step for `loop verify`
```

**Walkthrough (end to end).** During a session, Claude Code discovers that the repo needs `pnpm`, because `npm install` breaks postinstall hooks. The skill triggers. The model runs `loop propose --layer context --target AGENTS.md` with a three-line diff and attaches a `command-transcript` evidence record (fail, apply, pass). Policy says context = L2 with `reproducible_check`. The CLI verifies the transcript is reproducible, applies the diff, journals entry 412, and commits. Every later session — any agent, any harness in the org after `loop sync` — starts with the lesson. Time from lesson to fleet: minutes.

### 8.2 The creator door — custom agent builders

The spec surface for a builder: five JSON Schemas, the directory convention, the lifecycle, and the conformance suite. The SDK (Python and TypeScript) wraps the same library as the CLI, so both doors produce identical files.

```python
from loop import Loop

loop = Loop(".loop")                       # opens policy + journal
cs = loop.propose(layer="context",
                  targets=["prompts/system.md"],
                  diff=patch, origin=run_id,
                  rationale="Tickets in category X need the customer ID first.")
cs.attach_evidence(inspect_report)          # Inspect / lm-eval / OTel / transcript
decision = loop.gate(cs)                    # deterministic policy evaluation
if decision.approved:
    loop.apply(cs)                          # snapshot, apply, journal
else:
    loop.queue_for_review(cs)               # L1 path
```

Five verbs cover the loop: `propose`, `attach_evidence`, `gate`, `apply`, `rollback` (plus `log` to query and `sync` for Team). The embedding rule for an existing agent: find every place the code mutates a prompt, a memory store, or a tool — and replace the direct write with propose → gate → apply. Acceptance test for the spec: a builder implements or embeds a conformant Executor in under one day, and proves it with the golden-file conformance suite (known ChangeSets in, expected journal out).

### 8.3 Producer adapters

Optimizers become Producers with thin exporters: DSPy emits its compiled-program JSON as a context-layer ChangeSet; GEPA emits an evolved prompt as a diff with its trace-based evidence; a memory system emits consolidation writes as gated context changes. The standard does not compete with optimizers. It makes their outputs portable, comparable, and governable.

### 8.4 The launch demo: one lesson, two runtimes

One repo. Claude Code learns the pnpm lesson and produces a ChangeSet (door one). A custom agent built with the SDK pulls it through the same `.loop/` folder, gates it against its own policy, and applies it to its own prompt file (door two). One improvement crosses two independent runtimes with a full audit trail. That demo is the standard's existence proof, and it must ship on launch day.

### 8.5 Dogfood rule

The drop-in skill and the CLI update themselves through ChangeSets at L1. The standard improves through the standard. `policy.yaml` and the journal stay out of reach (I1) — the loop governs the agent; humans govern the loop.

## 9. Security: invariants and threat model

**Invariants (normative):**
- **I1 — No self-hosting.** `.loop/**` is never a valid target. Policy changes are human-only, architecture-class, journaled.
- **I2 — Append-only journal.** Entries are hash-chained; deletion or edit breaks verification.
- **I3 — No self-graded promotion.** L2/L3 application requires at least one `independent` evidence record.
- **I4 — Allowlisted targets.** A ChangeSet touching a path outside `targets_allow` fails validation.
- **I5 — Rollback always available.** Every applied ChangeSet must be reversible with one command.
- **I6 — Signed distribution.** (Team+) A Distributor serves only signed ChangeSets with provenance.

**Threats → mitigations:**

| # | Threat (documented basis) | Mitigation |
|---|---|---|
| T1 | Eval gaming / reward hacking (DGM removed its own detection markers) | I3; held-out checks; grader ≠ producer; reproducible_check gate |
| T2 | Memory poisoning, persistent prompt injection (MINJA-class attacks) | Context writes gated + journaled; I4 allowlists; origin/trigger recorded in provenance |
| T3 | Malicious skills, supply chain (MCP tool poisoning, rug pulls) | I6 signing; in-toto provenance; registry review status; local gates never bypassed (5.5) |
| T4 | Loop self-capture (agent edits its own policy or journal) | I1; I2; `loop verify` in CI |
| T5 | Injected proposals (a hostile webpage tells the agent to propose a backdoor) | L1 human review for capability/architecture; I4; evidence must reproduce; rationale + diff are small and reviewable |
| T6 | Journal tampering | Hash chain (Core); Merkle transparency log + signatures (Governed); CI verification |

## 10. Specification table of contents (the spec itself)

1. Introduction and problem statement · 2. Terminology and conformance language (RFC 2119) · 3. Conformance: roles × profiles · 4. The file plane · 5. ChangeSet · 6. Evidence · 7. Policy and trust levels · 8. Journal · 9. Lifecycle · 10. Registry and distribution (Team) · 11. Security considerations (invariants, threats) · 12. Regulatory mapping annex (EU AI Act Arts. 12/19/25/43(4), FDA PCCP, ISO/IEC 42001, NIST AI RMF) · 13. Normative JSON Schemas · 14. Conformance test suite · Appendix A: harness integration notes (Claude Code, AGENTS.md tools) · Appendix B: producer adapter guide.

## 11. Reference implementation plan

1. **Schemas + validator** (the smallest useful artifact; enables independent implementations immediately).
2. **`loop` CLI** — the reference Executor: init, propose, evidence, gate, apply, rollback, log, verify, sync.
3. **The drop-in skill** — built and tested with skill-authoring best practice (assertive description; scripts bundled; under 500 lines).
4. **Conformance suite** — golden files; the thing that lets a vendor say "we are compliant."
5. **SDK (Python, TypeScript)** — wraps the CLI's library.
6. **Producer adapters** — DSPy exporter first, GEPA second.
7. **Registry over a git remote**, then the OCI upgrade path.

## 12. Twelve-month roadmap

- **M1–M2:** Spec v0.1 draft + schemas public (Community Specification License). CLI executor + `loop verify`. Conformance suite v0.
- **M3 — Launch:** drop-in skill + `init`; the "one lesson, two runtimes" demo; announcement post built on the Section 1 problem statement; submit a "self-modification span" proposal to OpenTelemetry GenAI conventions.
- **M4–M6:** Team profile (git-remote registry, signing); DSPy and GEPA adapters; target: three independent Executor implementations exchanging one ChangeSet.
- **M7–M9:** Governed profile (transparency log, Rego gates, PCCP / Art. 43(4) mapping annex); one pilot with a compliance-sensitive organization.
- **M10–M12:** v1.0 freeze; conformance badge; move governance to the Joint Development Foundation or Linux Foundation once three or more organizations contribute.

## 13. Name candidates (live collision check required before announcement)

| Candidate | Why | Risk flags |
|---|---|---|
| **Ratchet** | The mechanism: forward motion, no slip back. Matches gates + rollback + escalation exactly | Game franchise; slang; check registries |
| **Lamarck** | Acquired traits become inherited — the precise metaphor for deployment-time learning | Bioinformatics tools use the name |
| **Cairn** | Stones stacked to mark the path for the next traveler; each ChangeSet is a stone | Crypto/game collisions to check |
| **SAIL** (Standard for Agent Improvement Loops) | Clean acronym | Collides with Stanford AI Lab — likely avoid |
| **OAIP** (Open Agent Improvement Protocol) | Safe, descriptive fallback | Forgettable |

Avoid per research: ACP (taken), SIP (taken), bare "ChangeSet" as a public name. The dotted directory (`.ratchet/`, `.cairn/`, …) follows the final name.

## 14. Open items to verify (carried from the research brief)

EU Digital Omnibus outcome and the real high-risk enforcement dates; MCP 2026 governance and latest spec version; MCP registry status; any 2026 self-improving-agent systems or competing standards; A2A current version; Claude Code hooks/skills current mechanics (docs.claude.com); AGENTS.md 2026 governance; exact DGM/AlphaEvolve/GEPA figures against the primary papers; name collision checks (Section 13). None of these blocks drafting the spec; all of them block the public announcement.
