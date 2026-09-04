"""Install the drop-in Claude Code skill and hooks (design §8.1, story B1).

Copies skill/SKILL.md into .claude/skills/monumentum/, the hook scripts into
.claude/hooks/, and merges the hook wiring into .claude/settings.json
idempotently.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_SRC = _REPO_ROOT / "skill"

GUARD_COMMAND = 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/pretooluse_guard.py"'
STOP_COMMAND = 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop_reminder.py"'


class SkillInstallError(Exception):
    pass


def install_skill(claude_dir: Path, skill_src: Path | None = None) -> list[str]:
    """Returns human-readable lines describing what was installed."""
    src = skill_src or SKILL_SRC
    if not (src / "SKILL.md").is_file():
        raise SkillInstallError(f"skill source not found at {src}")
    out: list[str] = []

    skill_dest = claude_dir / "skills" / "monumentum"
    skill_dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / "SKILL.md", skill_dest / "SKILL.md")
    out.append(f"skill installed: {skill_dest / 'SKILL.md'}")

    hooks_dest = claude_dir / "hooks"
    hooks_dest.mkdir(parents=True, exist_ok=True)
    for script in ("pretooluse_guard.py", "stop_reminder.py"):
        shutil.copyfile(src / "hooks" / script, hooks_dest / script)
        out.append(f"hook script installed: {hooks_dest / script}")

    settings_path = claude_dir / "settings.json"
    settings = {}
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    changed = _merge_hooks(settings)
    if changed:
        settings_path.write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        out.append(f"hooks wired in {settings_path}")
    else:
        out.append(f"hooks already wired in {settings_path}")
    return out


def _merge_hooks(settings: dict) -> bool:
    """Idempotent merge of the guard and reminder hooks. True if changed."""
    hooks = settings.setdefault("hooks", {})
    changed = False

    pre = hooks.setdefault("PreToolUse", [])
    if not _has_command(pre, GUARD_COMMAND):
        pre.append({
            "matcher": "Edit|Write|MultiEdit|NotebookEdit",
            "hooks": [{"type": "command", "command": GUARD_COMMAND}],
        })
        changed = True

    stop = hooks.setdefault("Stop", [])
    if not _has_command(stop, STOP_COMMAND):
        stop.append({
            "hooks": [{"type": "command", "command": STOP_COMMAND}],
        })
        changed = True
    return changed


def _has_command(groups: list, command: str) -> bool:
    for group in groups:
        for hook in group.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False
