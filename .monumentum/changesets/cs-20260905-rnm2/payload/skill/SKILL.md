---
name: monumentum
description: Govern durable lessons and self-improvements through the Monumentum standard. Use whenever you learn a lasting lesson about this repo (a command that fails and its working replacement, a convention, a fix for a broken skill or tool), whenever the user corrects you about repo behavior twice, whenever the user says "remember this", and near the end of a long session with unrecorded lessons. Never edit AGENTS.md, CLAUDE.md, memory files, skills, or tools directly in this workspace - propose a ChangeSet with the monumentum CLI instead.
---

# The Loop: propose, don't edit

This workspace is governed by the Monumentum standard (`.monumentum/`). Files that steer
agents (AGENTS.md, CLAUDE.md, memory, skills, tools, agent config) are
**monumentum-managed**: direct edits are denied by a PreToolUse hook and detected
by `monumentum verify` in CI. Durable lessons travel as evidence-backed
ChangeSets instead.

## When to propose

- You discovered a command, flag, or convention that future sessions need
  (e.g. `npm install` fails here, `pnpm install` works).
- The user corrected you about repo behavior, especially twice.
- A skill or tool script in this repo is broken and you know the fix.
- The user says "remember this" or asks to update AGENTS.md/CLAUDE.md.

Do NOT propose secrets, one-off task state, or anything you could not back
with evidence.

## How to propose (deterministic steps)

1. Write the change as a unified diff against the target file, e.g.
   `lesson.patch`. Keep it minimal.
2. Propose it:

   ```
   monumentum propose --layer context --target AGENTS.md --patch lesson.patch \
     --rationale "<one sentence: what breaks, what works>" \
     --producer claude-code --trigger reflection
   ```

   Layers: `context` (AGENTS.md, CLAUDE.md, memory), `capability`
   (skills, tools), `architecture` (agent config). The command prints the
   ChangeSet id (`cs-...`).

3. Attach evidence. The cheap, strong form is a command transcript: run the
   failing command, note the exit code, and record the check that must pass
   after the change. Write `transcript.json`:

   ```json
   {
     "check_cmd": "<command that exits 0 once the lesson is applied>",
     "runs": [
       {"phase": "before", "exit_code": 1},
       {"phase": "after", "exit_code": 0}
     ]
   }
   ```

   And an evidence record `ev.json`:

   ```json
   {
     "id": "ev-001", "kind": "eval", "grader": "independent",
     "format": "command-transcript",
     "summary": {"metric": "task_pass", "before": 0, "after": 1, "n": 1}
   }
   ```

   Then: `monumentum evidence <cs-id> --record ev.json --artifact transcript.json`

4. Gate and apply:

   ```
   monumentum gate <cs-id>
   monumentum apply <cs-id>    # only if gate printed GATE_APPROVED
   ```

   Exit code 2 from `gate` means the change is queued for human review
   (capability and architecture changes always queue). Tell the user it is
   queued and stop; a human runs `monumentum approve <cs-id> --actor human/<name>`.

5. If anything is rejected, read the reason, fix the ChangeSet or the
   evidence, and propose again. Never work around the gate by editing the
   file directly.

## Quick reference

- `monumentum status` - queue and change states
- `monumentum log` - the journal (who changed what, when, why)
- `monumentum rollback <cs-id>` - one-command revert of an applied change
- `monumentum verify .` - integrity check (journal chain + managed files)
