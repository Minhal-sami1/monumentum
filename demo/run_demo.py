#!/usr/bin/env python
"""One lesson, two runtimes (story B4; design §8.4). The existence proof.

Runtime A (the consumer door): a scripted producer session drives the
real monumentum CLI in fixture repo A. It learns the pnpm lesson, proposes
a ChangeSet with a command transcript, and the L2 gate applies it.

Runtime B (the creator door): the toy SDK agent in workspace B receives
that ChangeSet folder (Core-profile handoff), gates it against ITS OWN
policy, and applies the lesson to ITS OWN prompt file.

Assertions cover both end states and both journals. The wall-clock
lesson-to-second-runtime time is logged to experiments/interop/logs/.

Everything runs as real subprocesses; nothing is mocked.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOY_AGENT = REPO / "sdk" / "examples" / "toy_agent.py"

AGENTS_MD = "# Agent notes\n\nUse npm install to set up.\n"
FIX_PATCH = """\
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up. npm install fails on postinstall hooks.
"""
RATIONALE = "Repo uses pnpm. npm install fails on postinstall hooks."


def sh(cmd: list[str], cwd: Path, expect: int = 0) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    if proc.returncode != expect:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"demo step failed ({' '.join(map(str, cmd))}): exit {proc.returncode}")
    return proc


def main() -> int:
    py = sys.executable
    cli = [py, "-m", "monumentum.cli"]
    run_id = f"demo-{dt.datetime.now(dt.UTC):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    root = Path(tempfile.mkdtemp(prefix="monumentum-demo-"))
    ws_a = root / "runtime-a"
    ws_b = root / "runtime-b"
    ws_a.mkdir(parents=True)

    print("=== Runtime A (consumer door: real CLI) ===")
    (ws_a / "AGENTS.md").write_text(AGENTS_MD, encoding="utf-8", newline="\n")
    (ws_a / "fix.patch").write_text(FIX_PATCH, encoding="utf-8", newline="\n")
    (ws_a / "ev.json").write_text(json.dumps({
        "id": "ev-001", "kind": "eval", "grader": "independent",
        "format": "command-transcript",
        "summary": {"metric": "task_pass", "before": 0, "after": 1, "n": 1},
    }), encoding="utf-8")
    (ws_a / "transcript.json").write_text(json.dumps({
        "check_cmd": (
            'python -c "import sys; '
            "sys.exit(0 if 'pnpm' in open('AGENTS.md', encoding='utf-8').read() else 1)\""
        ),
        "runs": [{"phase": "before", "exit_code": 1}, {"phase": "after", "exit_code": 0}],
    }), encoding="utf-8")

    sh([*cli, "init"], ws_a)
    cs_a = "cs-20260831-demo1"

    t0_wall = dt.datetime.now(dt.UTC).isoformat()
    t0 = time.monotonic()  # the lesson exists now; the clock starts

    sh([*cli, "propose", "--layer", "context", "--target", "AGENTS.md",
        "--patch", "fix.patch", "--rationale", RATIONALE,
        "--producer", "claude-code-scripted", "--trigger", "reflection",
        "--id", cs_a], ws_a)
    sh([*cli, "evidence", cs_a, "--record", "ev.json", "--artifact", "transcript.json"], ws_a)
    sh([*cli, "gate", cs_a], ws_a)
    sh([*cli, "apply", cs_a], ws_a)
    print(f"runtime A applied {cs_a}")

    print("=== Handoff (Core profile: the ChangeSet folder travels) ===")
    handoff = root / "handoff" / cs_a
    shutil.copytree(ws_a / ".monumentum" / "changesets" / cs_a, handoff)
    # the snapshot is runtime-A state, not part of the portable ChangeSet
    shutil.rmtree(handoff / "snapshot", ignore_errors=True)

    print("=== Runtime B (creator door: toy SDK agent) ===")
    sh([py, str(TOY_AGENT), "init", "--workspace", str(ws_b)], REPO)
    sh([py, str(TOY_AGENT), "ingest", "--workspace", str(ws_b),
        "--changeset", str(handoff)], REPO)

    t1 = time.monotonic()
    t1_wall = dt.datetime.now(dt.UTC).isoformat()
    elapsed = t1 - t0

    print("=== Assertions ===")
    failures: list[str] = []

    agents_a = (ws_a / "AGENTS.md").read_text(encoding="utf-8")
    if "pnpm install" not in agents_a:
        failures.append("runtime A: AGENTS.md does not carry the lesson")

    prompt_b = (ws_b / "prompts" / "system.md").read_text(encoding="utf-8")
    if cs_a not in prompt_b or "pnpm" not in prompt_b:
        failures.append("runtime B: prompt file does not carry the lesson")

    def events(ws: Path) -> list[dict]:
        out = []
        for f in sorted((ws / ".monumentum" / "journal").glob("*.ndjson")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.append(json.loads(line))
        return out

    events_a = [e["event"] for e in events(ws_a)]
    if events_a != ["genesis", "proposed", "gated", "applied"]:
        failures.append(f"runtime A journal unexpected: {events_a}")
    events_b = [e["event"] for e in events(ws_b)]
    if events_b != ["genesis", "proposed", "gated", "applied"]:
        failures.append(f"runtime B journal unexpected: {events_b}")

    for name, ws in (("A", ws_a), ("B", ws_b)):
        proc = subprocess.run([*cli, "-C", str(ws), "verify"],
                              capture_output=True, text=True, cwd=ws)
        if proc.returncode != 0:
            failures.append(f"runtime {name}: verify failed: {proc.stderr}")

    log_dir = REPO / "experiments" / "interop" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": run_id,
        "experiment": "interop",
        "t0_lesson_proposed": t0_wall,
        "t1_second_runtime_applied": t1_wall,
        "lesson_to_second_runtime_seconds": round(elapsed, 3),
        "changeset": cs_a,
        "runtime_a": "monumentum-cli",
        "runtime_b": "toy-sdk-agent",
        "python": sys.version.split()[0],
        "ok": not failures,
    }
    with open(log_dir / f"{run_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print(f"demo OK: one lesson crossed two runtimes in {elapsed:.2f}s "
          f"(logged: experiments/interop/logs/{run_id}.jsonl)")
    shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
