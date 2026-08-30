"""Skill + hook installation tests (B1 packaging, B2 idempotency)."""

import json

from agentloop.skill_install import GUARD_COMMAND, install_skill
from agentloop.workspace import ensure_agents_block


def test_install_skill_and_hooks(tmp_path):
    claude_dir = tmp_path / ".claude"
    install_skill(claude_dir)
    assert (claude_dir / "skills" / "loop" / "SKILL.md").is_file()
    assert (claude_dir / "hooks" / "pretooluse_guard.py").is_file()
    assert (claude_dir / "hooks" / "stop_reminder.py").is_file()
    settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    pre = settings["hooks"]["PreToolUse"]
    assert any(GUARD_COMMAND == h["command"] for g in pre for h in g["hooks"])
    assert settings["hooks"]["Stop"]


def test_install_skill_idempotent(tmp_path):
    claude_dir = tmp_path / ".claude"
    install_skill(claude_dir)
    first = (claude_dir / "settings.json").read_text(encoding="utf-8")
    install_skill(claude_dir)
    assert (claude_dir / "settings.json").read_text(encoding="utf-8") == first
    settings = json.loads(first)
    assert len(settings["hooks"]["PreToolUse"]) == 1


def test_install_preserves_existing_settings(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps({"model": "opus", "hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}
        ]}}),
        encoding="utf-8",
    )
    install_skill(claude_dir)
    settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert settings["model"] == "opus"
    commands = [h["command"] for g in settings["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert "echo hi" in commands and GUARD_COMMAND in commands


def test_agents_block_created_and_idempotent(tmp_path):
    assert ensure_agents_block(tmp_path) is True
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert content.count("agentloop:managed:begin") == 1
    assert ensure_agents_block(tmp_path) is False
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == content


def test_agents_block_appends_to_existing(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Existing notes\n", encoding="utf-8")
    ensure_agents_block(tmp_path)
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert content.startswith("# Existing notes")
    assert content.count("agentloop:managed:begin") == 1
