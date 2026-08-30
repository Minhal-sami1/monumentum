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


AGENTS_BLOCK_BEGIN = "<!-- agentloop:managed:begin -->"
AGENTS_BLOCK_END = "<!-- agentloop:managed:end -->"

AGENTS_BLOCK = f"""{AGENTS_BLOCK_BEGIN}
## Governed self-improvement (agentloop)

This workspace is governed by the Loop standard. Rules for every agent:

1. Do NOT edit loop-managed files directly (AGENTS.md, CLAUDE.md, memory,
   skills, tools, agent config). Policy lists the exact patterns in
   `.loop/policy.yaml`.
2. When you learn a durable lesson, propose it instead:
   `agentloop propose --layer context --target <file> --patch <diff> --rationale "<why>"`
3. Attach evidence (fail -> apply -> pass transcript):
   `agentloop evidence <cs-id> --record <ev.json> --artifact <transcript>`
4. Gate and apply: `agentloop gate <cs-id>` then `agentloop apply <cs-id>`.
   Low-risk context changes auto-apply with independent evidence; capability
   and architecture changes queue for human review.
5. Never touch `.loop/**`. Verify integrity anytime: `agentloop verify .`
{AGENTS_BLOCK_END}"""


def ensure_agents_block(root: Path) -> bool:
    """Append the managed contract block to AGENTS.md once. Idempotent:
    if the begin marker exists, the file is left byte-identical.
    Returns True when the file changed."""
    path = root / "AGENTS.md"
    if path.is_file():
        content = path.read_text(encoding="utf-8")
        if AGENTS_BLOCK_BEGIN in content:
            return False
        joiner = "" if content.endswith("\n\n") else ("\n" if content.endswith("\n") else "\n\n")
        content = content + joiner + AGENTS_BLOCK + "\n"
    else:
        content = AGENTS_BLOCK + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


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
