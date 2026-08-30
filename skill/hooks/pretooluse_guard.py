#!/usr/bin/env python3
"""PreToolUse guard: deny direct Edit/Write on loop-managed files.

Contract (verified against code.claude.com/docs/en/hooks, see DEC-017):
reads the hook JSON from stdin; exit 2 blocks the tool call and stderr
becomes the message Claude sees; exit 0 means no decision.

Stdlib only: managed patterns come from .loop/state.json
(`managed_patterns`, executor-written), with a PyYAML fallback to
.loop/policy.yaml when available (DEC-018).
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys


def find_loop_root(start: str) -> str | None:
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, ".loop")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def load_patterns(root: str) -> list[str]:
    state_path = os.path.join(root, ".loop", "state.json")
    try:
        with open(state_path, encoding="utf-8") as f:
            patterns = json.load(f).get("managed_patterns", [])
        if patterns:
            return patterns
    except OSError:
        pass
    try:  # fallback: parse the policy directly if PyYAML is available
        import yaml

        with open(os.path.join(root, ".loop", "policy.yaml"), encoding="utf-8") as f:
            policy = yaml.safe_load(f)
        patterns = list(policy.get("protected", []))
        for cls in (policy.get("envelope") or {}).values():
            patterns.extend(cls.get("targets_allow", []))
        return patterns
    except Exception:
        return []


def glob_match(target: str, pattern: str) -> bool:
    if fnmatch.fnmatch(target, pattern):
        return True
    return bool(pattern.endswith("/**") and fnmatch.fnmatch(target, pattern[:-3] + "/*"))


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("hook_event_name") != "PreToolUse":
        return 0
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return 0
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return 0
    root = find_loop_root(data.get("cwd") or os.getcwd())
    if root is None:
        return 0
    rel = os.path.relpath(os.path.abspath(file_path), root).replace("\\", "/")
    if rel.startswith(".."):
        return 0
    managed = rel.startswith(".loop/") or rel == ".loop" or any(
        glob_match(rel, p) for p in load_patterns(root)
    )
    if not managed:
        return 0
    sys.stderr.write(
        f"'{rel}' is loop-managed; direct edits are denied by policy (Loop standard).\n"
        f"Propose the change instead:\n"
        f"  agentloop propose --layer <context|capability|architecture> "
        f"--target {rel} --patch <diff-file> --rationale \"<why>\"\n"
        f"then attach evidence and gate it:\n"
        f"  agentloop evidence <cs-id> --record <ev.json> --artifact <transcript>\n"
        f"  agentloop gate <cs-id> && agentloop apply <cs-id>\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
