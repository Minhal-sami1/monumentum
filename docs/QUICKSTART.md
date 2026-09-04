# QUICKSTART — govern your first self-improvement in 10 minutes

This is the consumer path. Commands are copy-paste and are exercised by
`make quickstart-test`, so they stay correct.

## 0. Install

```
pip install -e .            # from the repo; or `pip install monumentum` once published
monumentum --version
```

## 1. Govern a workspace

From your project root (one that has an `AGENTS.md` or `CLAUDE.md`):

```
monumentum init
```

This scaffolds `.monumentum/` (default policy: context L2, capability L1,
architecture L1), writes a genesis journal entry, and appends a managed
contract block to `AGENTS.md`. It prints the next steps.

## 2. Draft a change as a diff

Say `AGENTS.md` tells agents to run `npm install`, but `pnpm install` is
what actually works. Write the fix as a unified diff, `lesson.patch`:

```
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up. npm install fails on postinstall hooks.
```

## 3. Propose it

```
monumentum propose --layer context --target AGENTS.md --patch lesson.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks." \
  --producer me
```

The command prints a ChangeSet id (`cs-...`). Nothing is applied yet.

## 4. Attach evidence (fail -> apply -> pass)

Record the check that must pass once the lesson is in place, as
`transcript.json`:

```
{
  "check_cmd": "grep -q 'pnpm install' AGENTS.md",
  "runs": [ { "phase": "before", "exit_code": 1 }, { "phase": "after", "exit_code": 0 } ]
}
```

And an evidence record, `ev.json`:

```
{
  "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "task_pass", "before": 0, "after": 1, "n": 1 }
}
```

Attach them (the artifact hash is computed for you):

```
monumentum evidence <cs-id> --record ev.json --artifact transcript.json
```

## 5. Gate and apply

```
monumentum gate <cs-id>     # prints GATE_APPROVED for a context change with independent evidence
monumentum apply <cs-id>    # snapshots, applies, journals, commits
```

Context changes at L2 auto-apply once independent evidence reproduces.
Capability and architecture changes queue for a human:
`monumentum approve <cs-id> --actor human/you`.

## 6. Audit and undo

```
monumentum log            # who changed what, when, and why
monumentum verify .       # journal chain intact + managed files match
monumentum rollback <cs-id>   # one command back to the exact prior bytes
```

## 7. Claude Code users: install the skill

```
monumentum install-skill
```

This installs the `loop` skill and a `PreToolUse` hook that denies direct
edits to managed files (pointing the agent at `monumentum propose`), plus a
session-end reminder for queued changes.

## Universal backstop: CI

Add one line to CI so no ungoverned change reaches your main branch:

```
monumentum verify .
```
