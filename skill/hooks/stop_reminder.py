#!/usr/bin/env python3
"""Stop hook: surface queued ChangeSets when a session ends its turn.

Exit 0 with a `systemMessage` (shown to the user); never blocks the stop.
Stdlib only. See DEC-017: SessionEnd cannot carry messages reliably, so
the reminder lives on Stop.
"""

from __future__ import annotations

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


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    root = find_loop_root(data.get("cwd") or os.getcwd())
    if root is None:
        return 0
    try:
        with open(os.path.join(root, ".loop", "state.json"), encoding="utf-8") as f:
            queue = json.load(f).get("queue", [])
    except OSError:
        return 0
    if queue:
        print(json.dumps({
            "systemMessage": (
                f"agentloop: {len(queue)} change(s) queued for review: "
                + ", ".join(queue)
                + ". Review with: agentloop status; approve with: "
                  "agentloop approve <cs-id> --actor human/<name>"
            )
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
