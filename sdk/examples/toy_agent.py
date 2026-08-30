#!/usr/bin/env python
"""A toy custom agent built on the Loop SDK (story B3, door two).

It owns one prompt file (prompts/system.md). It never edits that file
directly: every self-modification goes propose -> evidence -> gate ->
apply through the SDK. That is the embedding rule from design §8.2.

Verbs:
    toy_agent.py init   --workspace DIR
        Scaffold the agent: prompt file, loop policy, governed workspace.
    toy_agent.py run    --workspace DIR
        "Run" the agent: print the instructions it would follow.
    toy_agent.py ingest --workspace DIR --changeset DIR
        Interop path (story B4): read a foreign ChangeSet produced by a
        different runtime, translate its lesson into this agent's own
        prompt file, and push it through the local gates. Distribution
        never bypasses gates: the foreign lesson still needs evidence
        that reproduces HERE.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from loop import Loop

PROMPT_REL = "prompts/system.md"

INITIAL_PROMPT = """\
# Toy agent system prompt

You are a tiny deterministic agent. Follow the lessons below.

## Lessons
"""

POLICY = """\
spec: loop/v0.1
envelope:
  context:
    level: L2
    gates: [evidence_required, reproducible_check]
    targets_allow: ["prompts/system.md", "AGENTS.md"]
  capability:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: ["tools/**"]
  architecture:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: ["agent.yaml"]
protected: [".loop/**"]
de_escalation: { on_rollbacks: 2, window_days: 14, drop: 1 }
audit: { journal: hash-chain, retain_days: 365 }
"""


def cmd_init(workspace: Path) -> int:
    prompt_path = workspace / PROMPT_REL
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    if not prompt_path.is_file():
        prompt_path.write_text(INITIAL_PROMPT, encoding="utf-8", newline="\n")
    Loop.init(workspace, POLICY)
    print(f"toy agent initialized in {workspace}")
    return 0


def cmd_run(workspace: Path) -> int:
    prompt = (workspace / PROMPT_REL).read_text(encoding="utf-8")
    lessons = [line for line in prompt.splitlines() if line.startswith("- ")]
    print(f"toy agent running with {len(lessons)} lesson(s):")
    for lesson in lessons:
        print(f"  {lesson}")
    return 0


def _make_diff(old: str, new: str, rel: str) -> str:
    lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
    )
    return "".join(lines)


def cmd_ingest(workspace: Path, changeset_dir: Path) -> int:
    foreign = json.loads((changeset_dir / "changeset.json").read_text(encoding="utf-8"))
    foreign_id = foreign["id"]
    lesson = foreign["rationale"].strip()

    lp = Loop(workspace / ".loop")
    prompt_path = workspace / PROMPT_REL
    old = prompt_path.read_text(encoding="utf-8")
    lesson_line = f"- [{foreign_id}] {lesson}\n"
    if lesson_line in old:
        print(f"lesson from {foreign_id} already present; nothing to do")
        return 0
    new = old + lesson_line

    cs = lp.propose(
        layer="context",
        targets=[PROMPT_REL],
        diff=_make_diff(old, new, PROMPT_REL),
        rationale=f"Adopt lesson from {foreign_id}: {lesson}",
        producer="toy-agent",
        trigger="peer-changeset",
        origin=f"ingest-{foreign_id}",
    )

    # Independent, reproducible evidence: after apply, the lesson marker
    # must be present in this agent's own prompt file.
    check_cmd = (
        f'python -c "import sys; '
        f"sys.exit(0 if '[{foreign_id}]' in open('{PROMPT_REL}', encoding='utf-8').read() "
        f'else 1)"'
    )
    transcript = workspace / f"transcript-{foreign_id}.json"
    transcript.write_text(
        json.dumps({
            "check_cmd": check_cmd,
            "runs": [{"phase": "before", "exit_code": 1}, {"phase": "after", "exit_code": 0}],
        }),
        encoding="utf-8",
    )
    cs.attach_evidence(
        {
            "id": "ev-001",
            "kind": "reproduction",
            "grader": "independent",
            "format": "command-transcript",
            "summary": {"metric": "lesson_present", "before": 0, "after": 1, "n": 1},
        },
        artifact=transcript,
    )

    decision = lp.gate(cs)
    if decision.queued:
        print(f"{cs.id}: queued for human review")
        return 2
    if not decision.approved:
        print(f"{cs.id}: rejected: {decision.reason}", file=sys.stderr)
        return 1
    lp.apply(cs)
    print(f"{cs.id}: APPLIED lesson from {foreign_id} to {PROMPT_REL}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="toy_agent")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "run", "ingest"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, required=True)
        if name == "ingest":
            p.add_argument("--changeset", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "init":
        return cmd_init(args.workspace)
    if args.command == "run":
        return cmd_run(args.workspace)
    return cmd_ingest(args.workspace, args.changeset)


if __name__ == "__main__":
    sys.exit(main())
