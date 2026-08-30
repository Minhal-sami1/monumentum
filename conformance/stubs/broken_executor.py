#!/usr/bin/env python
"""A deliberately broken executor (D2 negative test).

It speaks the subprocess contract but violates the standard: it applies
everything without gates, queues nothing, journals without a hash chain,
and always reports a clean verify. The conformance suite MUST fail it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(prog="broken-executor")
    parser.add_argument("-C", "--workspace", type=Path, default=Path("."))
    parser.add_argument("verb")
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    ws = args.workspace
    loop = ws / ".loop"

    def journal(event: str) -> None:
        loop.joinpath("journal").mkdir(parents=True, exist_ok=True)
        # No seq discipline, no prev hash: chain-free "journal".
        entry = {"event": event, "ts": datetime.now(UTC).isoformat()}
        with open(loop / "journal" / "log.ndjson", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    if args.verb == "init":
        loop.mkdir(parents=True, exist_ok=True)
        (loop / "policy.yaml").write_text("anything: goes\n", encoding="utf-8")
        (loop / "state.json").write_text("{}\n", encoding="utf-8")
        journal("genesis")
        return 0
    if args.verb == "propose":
        journal("proposed")
        return 0  # accepts everything, allowlists ignored
    if args.verb == "evidence":
        return 0  # evidence is decorative here
    if args.verb == "gate":
        journal("gated")
        return 0  # auto-approves everything; nothing ever queues
    if args.verb in ("apply", "approve"):
        journal("applied")
        # "applies" by appending a marker, ignoring the actual payload
        for candidate in ("AGENTS.md", "tools/helper.py"):
            path = ws / candidate
            if path.is_file():
                path.write_text(path.read_text(encoding="utf-8") + "# broken-apply\n",
                                encoding="utf-8")
        return 0
    if args.verb in ("reject", "rollback"):
        journal(args.verb)
        return 0
    if args.verb == "verify":
        return 0  # always claims to be fine
    if args.verb == "log":
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
