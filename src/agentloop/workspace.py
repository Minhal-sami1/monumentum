"""Workspace: the .loop/ directory and executor-managed state.json."""

from __future__ import annotations

import json
from pathlib import Path

from agentloop import __version__
from agentloop.hashing import sha256_bytes, sha256_file
from agentloop.journal import Journal

DEFAULT_POLICY = """\
# Default policy written by `agentloop init`. Only humans edit this file (I1).
spec: loop/v0.1
envelope:
  context:
    level: L2
    gates: [evidence_required, reproducible_check]
    targets_allow: ["AGENTS.md", "CLAUDE.md", ".claude/memory/**"]
  capability:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: [".claude/skills/**", "tools/**"]
  architecture:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: ["agents.yaml"]
protected: [".loop/**"]
escalation:
  capability: { to: L2, after: { applied: 20, rollbacks_max: 1, window_days: 30 } }
de_escalation: { on_rollbacks: 2, window_days: 14, drop: 1 }
audit: { journal: hash-chain, retain_days: 365 }
"""


class WorkspaceError(Exception):
    pass


def executor_actor() -> str:
    return f"executor/agentloop@{__version__}"


class Workspace:
    """A directory governed by one .loop/ folder."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.loop = self.root / ".loop"
        self.journal = Journal(self.loop / "journal")

    @property
    def policy_path(self) -> Path:
        return self.loop / "policy.yaml"

    @property
    def state_path(self) -> Path:
        return self.loop / "state.json"

    @property
    def changesets_dir(self) -> Path:
        return self.loop / "changesets"

    def exists(self) -> bool:
        return self.loop.is_dir() and self.policy_path.is_file()

    def require(self) -> None:
        if not self.exists():
            raise WorkspaceError(f"no .loop workspace at {self.root} (run: agentloop init)")

    # -- state.json --------------------------------------------------------

    def read_state(self) -> dict:
        if not self.state_path.is_file():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def write_state(self, state: dict) -> None:
        self.state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def update_journal_head(self, state: dict | None = None) -> dict:
        """Record the hash of the newest journal line so last-line tampering
        is detectable (the chain alone cannot protect its own tail)."""
        state = state if state is not None else self.read_state()
        last = self.journal.last_line()
        state["journal_head"] = sha256_bytes(last) if last else None
        return state

    # -- target helpers ----------------------------------------------------

    def target_abspath(self, target: str) -> Path:
        """Resolve a validated workspace-relative target path."""
        path = (self.root / target).resolve()
        if not str(path).startswith(str(self.root)):
            raise WorkspaceError(f"target escapes workspace: {target}")
        return path

    def target_hash(self, target: str) -> str | None:
        path = self.target_abspath(target)
        return sha256_file(path) if path.is_file() else None
