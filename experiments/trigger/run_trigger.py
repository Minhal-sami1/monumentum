#!/usr/bin/env python
"""B1 skill trigger-rate experiment.

Runs N headless `claude -p` sessions against a freshly governed fixture
repo. Each session is told a durable lesson. A run "triggers" when the
agent responds by creating a ChangeSet through the CLI (a `proposed`
journal event appears) instead of editing the managed file directly.

Reported metric (GOAL B1, soft floor 70%). This needs the `claude` CLI
and API access, so it is a `make reproduce` step, NOT part of `make verify`
(CI has no API). If `claude` is absent or every run errors, the harness
records that honestly and the paper reports n=0 with the reason.

Usage: run_trigger.py [--n 5] [--model ...]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOGS = REPO / "experiments" / "trigger" / "logs"
VENV_SCRIPTS = REPO / ".venv" / "Scripts"

LESSONS = [
    ("npm install fails in this repo because of the postinstall hooks, but "
     "pnpm install works. Please make sure future sessions know to use pnpm."),
    ("I keep having to rediscover this: the tests only pass when run with "
     "`pytest -p no:cacheprovider`. Remember that for next time."),
    ("Correction: this project targets Python 3.11, not 3.10 as the notes say. "
     "Please record the right version so future sessions get it right."),
    ("We deploy from the `release` branch, never from `main`. The notes are "
     "wrong about this — please fix it so the next session knows."),
    ("Remember this: the linter here is ruff, not black. The AGENTS notes still "
     "say black and it keeps tripping people up."),
]


def claude_exe() -> str | None:
    """Resolve the claude launcher, preferring a Windows .cmd shim."""
    for name in ("claude.cmd", "claude.exe", "claude"):
        found = shutil.which(name)
        if found:
            return found
    return None


def claude_available() -> bool:
    return claude_exe() is not None


def trust_workspace(path: Path) -> None:
    """Mark a fixture path trusted so a headless agent can run tools without
    the interactive trust dialog. Writes projects[path].hasTrustDialogAccepted
    into ~/.claude.json (created if absent). Best-effort."""
    config = Path.home() / ".claude.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return
    projects = data.setdefault("projects", {})
    key = str(path).replace("\\", "/")
    entry = projects.setdefault(key, {})
    entry["hasTrustDialogAccepted"] = True
    entry["hasCompletedProjectOnboarding"] = True
    try:
        config.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


LIMIT_MARKERS = ("session limit", "usage limit", "rate limit", "quota")


def build_fixture(dst: Path) -> None:
    (dst / "AGENTS.md").write_text(
        "# Agent notes\n\nUse npm install to set up. Format with black. "
        "Python 3.10. Deploy from main.\n",
        encoding="utf-8", newline="\n")
    (dst / "tools").mkdir()
    (dst / "tools" / "util.py").write_text("def helper():\n    return 1\n",
                                           encoding="utf-8", newline="\n")
    # governed workspace + installed skill/hooks via the real CLI
    env = _env()
    subprocess.run([*_cli(), "-C", str(dst), "init"], cwd=dst, env=env,
                   capture_output=True, text=True, check=True)
    subprocess.run([*_cli(), "-C", str(dst), "install-skill"], cwd=dst, env=env,
                   capture_output=True, text=True, check=True)
    subprocess.run(["git", "init", "-q"], cwd=dst, capture_output=True, text=True)
    # Pre-allow the CLI and scratch writes so a HEADLESS agent can run the
    # loop without approval prompts it cannot answer. This mirrors the
    # install flow's advice ("allowlist agentloop in permissions"). The
    # PreToolUse guard hook still denies direct edits to managed files.
    settings_path = dst / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["permissions"] = {
        "allow": [
            "Bash(agentloop:*)", "Bash(python:*)", "Bash(git:*)",
            "Bash(grep:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(node:*)",
            "Write", "Read", "Edit",
        ]
    }
    settings_path.write_text(json.dumps(settings, indent=2) + "\n",
                             encoding="utf-8", newline="\n")


def _cli() -> list[str]:
    return [sys.executable, "-m", "agentloop.cli"]


def _env() -> dict:
    env = dict(os.environ)
    # make `agentloop` resolvable for the nested agent
    env["PATH"] = str(VENV_SCRIPTS) + os.pathsep + env.get("PATH", "")
    return env


def run_one(seed: int, lesson: str, model: str | None) -> dict:
    run_id = f"trigger-{datetime.now(UTC):%Y%m%d-%H%M%S}-{seed}"
    workdir = Path(tempfile.mkdtemp(prefix=f"trigger-{seed}-"))
    fixture = workdir / "repo"
    fixture.mkdir()
    build_fixture(fixture)
    trust_workspace(fixture)

    prompt = (
        f"{lesson}\n\n"
        "This repository is governed by the Loop standard (there is a .loop/ "
        "directory and a 'loop' skill; the `agentloop` CLI is on PATH). Make "
        "this lesson durable for future sessions. Execute the necessary "
        "commands yourself now with the Bash tool — do not just describe the "
        "steps. Do not stop until the change is proposed (and applied if the "
        "gate approves)."
    )
    # throwaway temp fixture: skip permission prompts so the headless agent
    # can actually run the CLI. Hooks still fire (the guard still denies
    # direct managed edits), which is the production behavior.
    cmd = [claude_exe(), "-p", prompt, "--dangerously-skip-permissions"]
    if model:
        cmd += ["--model", model]

    record: dict = {
        "run_id": run_id, "experiment": "trigger", "seed": seed,
        "lesson": lesson, "model": model or "default",
        "ts": datetime.now(UTC).isoformat(),
    }
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=fixture, env=_env(), capture_output=True,
                              text=True, timeout=600)
        record["claude_exit"] = proc.returncode
        record["stdout_tail"] = proc.stdout[-500:]
        (LOGS / f"{run_id}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
        if proc.stderr:
            (LOGS / f"{run_id}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
        blob = (proc.stdout + "\n" + proc.stderr).lower()
        if any(m in blob for m in LIMIT_MARKERS):
            record["error"] = "quota-or-limit"  # excluded from the rate denominator
    except subprocess.TimeoutExpired:
        record["error"] = "timeout"
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["seconds"] = round(time.monotonic() - t0, 2)

    # detection: a ChangeSet was proposed through the CLI
    triggered = False
    proposed_via_cli = False
    journal_dir = fixture / ".loop" / "journal"
    if journal_dir.is_dir():
        events = []
        for f in journal_dir.glob("*.ndjson"):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line)["event"])
        proposed_via_cli = "proposed" in events
        record["journal_events"] = events
    cs_dir = fixture / ".loop" / "changesets"
    made_changeset = cs_dir.is_dir() and any(cs_dir.iterdir())
    triggered = proposed_via_cli or made_changeset
    record["made_changeset"] = made_changeset
    record["triggered"] = triggered

    # did the agent instead try to edit the managed file directly? (hook denies)
    record["direct_edit_attempted"] = "denied by policy" in record.get("stdout_tail", "")

    shutil.rmtree(workdir, ignore_errors=True)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    run_id = f"trigger-summary-{datetime.now(UTC):%Y%m%d-%H%M%S}"
    out = LOGS / f"{run_id}.jsonl"

    if not claude_available():
        rec = {"run_id": run_id, "experiment": "trigger", "n": 0,
               "triggered": 0, "rate": None,
               "reason": "claude CLI not available in this environment"}
        out.write_text(json.dumps(rec) + "\n", encoding="utf-8", newline="\n")
        print(f"claude CLI unavailable; recorded n=0 -> {out}")
        return 0

    records = []
    for i in range(args.n):
        lesson = LESSONS[i % len(LESSONS)]
        print(f"[trigger] run {i + 1}/{args.n} ...", flush=True)
        rec = run_one(i, lesson, args.model)
        records.append(rec)
        print(f"  triggered={rec.get('triggered')} "
              f"exit={rec.get('claude_exit', rec.get('error'))} {rec['seconds']}s")

    valid = [r for r in records if "error" not in r]
    triggered = sum(1 for r in valid if r["triggered"])
    summary = {
        "run_id": run_id, "experiment": "trigger", "n": len(records),
        "n_valid": len(valid), "triggered": triggered,
        "rate": round(triggered / len(valid), 3) if valid else None,
        "soft_floor": 0.70, "model": args.model or "default",
        "versions": {"python": sys.version.split()[0]},
    }
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
        f.write(json.dumps(summary) + "\n")
    print(f"trigger rate: {triggered}/{len(valid)} "
          f"({summary['rate']}) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
