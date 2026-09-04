"""HARD GATE (B1): the PreToolUse guard denies direct edits to managed
targets, and the Stop reminder surfaces the queue. Both scripts run as real
subprocesses with the documented stdin contract (DEC-017)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from monumentum.executor import init_workspace

REPO = Path(__file__).resolve().parents[1]
GUARD = REPO / "skill" / "hooks" / "pretooluse_guard.py"
REMINDER = REPO / "skill" / "hooks" / "stop_reminder.py"


@pytest.fixture
def ws_root(tmp_path) -> Path:
    (tmp_path / "AGENTS.md").write_text("# notes\n", encoding="utf-8")
    init_workspace(tmp_path)
    return tmp_path


def _run_guard(ws_root: Path, tool_name: str, file_path: str) -> subprocess.CompletedProcess:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(ws_root / file_path)},
        "cwd": str(ws_root),
        "session_id": "test",
    }
    return subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=60,
    )


def test_guard_denies_edit_on_managed_file(ws_root):
    proc = _run_guard(ws_root, "Edit", "AGENTS.md")
    assert proc.returncode == 2
    assert "loop-managed" in proc.stderr
    assert "monumentum propose" in proc.stderr


def test_guard_denies_write_on_loop_dir(ws_root):
    proc = _run_guard(ws_root, "Write", ".monumentum/policy.yaml")
    assert proc.returncode == 2


def test_guard_denies_skills_pattern(ws_root):
    proc = _run_guard(ws_root, "Write", ".claude/skills/monumentum/SKILL.md")
    assert proc.returncode == 2


def test_guard_allows_unmanaged_file(ws_root):
    proc = _run_guard(ws_root, "Edit", "src/main.py")
    assert proc.returncode == 0
    assert proc.stderr == ""


def test_guard_allows_outside_governed_workspace(tmp_path):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "AGENTS.md")},
        "cwd": str(tmp_path),
    }
    proc = subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0


def test_guard_ignores_other_tools(ws_root):
    proc = _run_guard(ws_root, "Read", "AGENTS.md")
    assert proc.returncode == 0


def _run_reminder(ws_root: Path) -> subprocess.CompletedProcess:
    payload = {"hook_event_name": "Stop", "cwd": str(ws_root)}
    return subprocess.run(
        [sys.executable, str(REMINDER)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=60,
    )


def test_reminder_quiet_when_queue_empty(ws_root):
    proc = _run_reminder(ws_root)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_reminder_reports_queued_changesets(ws_root):
    state_path = ws_root / ".monumentum" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["queue"] = ["cs-20260830-q001"]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proc = _run_reminder(ws_root)
    assert proc.returncode == 0
    message = json.loads(proc.stdout)
    assert "cs-20260830-q001" in message["systemMessage"]
