"""Loop SDK: the five verbs for custom agent builders (design §8.2, story B3).

    from loop import Loop

    lp = Loop(".loop")                     # opens policy + journal
    cs = lp.propose(layer="context", targets=["prompts/system.md"],
                    diff=patch_text, rationale="...", origin="run-42")
    cs.attach_evidence(record, artifact="transcript.json")
    decision = lp.gate(cs)
    if decision.approved:
        lp.apply(cs)
    elif decision.queued:
        lp.queue_for_review(cs)            # already queued by gate; returns id

The SDK wraps the same library as the CLI, so both doors produce
identical files.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from agentloop import executor as _executor
from agentloop.changeset import (
    attach_evidence as _attach_evidence,
)
from agentloop.changeset import (
    create_changeset,
    ingest_changeset,
    load_changeset,
)
from agentloop.workspace import Workspace

__all__ = ["Loop", "ChangeSetHandle", "Decision", "LoopError"]


class LoopError(Exception):
    pass


@dataclass
class Decision:
    approved: bool
    queued: bool
    status: str
    reason: str = ""


class ChangeSetHandle:
    def __init__(self, loop: Loop, folder: Path):
        self._loop = loop
        self._folder = folder

    @property
    def id(self) -> str:
        return load_changeset(self._folder).id

    @property
    def envelope(self) -> dict:
        return load_changeset(self._folder).envelope

    def attach_evidence(self, record: dict | str | Path, artifact: str | Path | None = None):
        """Attach one evidence record (a dict or a JSON file path) and an
        optional artifact file. Artifact hashes are computed for you."""
        cs = load_changeset(self._folder)
        if isinstance(record, dict):
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(record, f)
                record_path = Path(f.name)
        else:
            record_path = Path(record)
        artifact_path = Path(artifact) if artifact is not None else None
        _attach_evidence(cs, record_path, artifact_path)
        return self


class Loop:
    """One governed workspace, addressed by its .loop directory."""

    def __init__(self, loop_dir: str | Path = ".loop"):
        loop_path = Path(loop_dir).resolve()
        self.workspace = Workspace(loop_path.parent)
        if not self.workspace.exists():
            raise LoopError(
                f"no governed workspace at {loop_path} (run Loop.init or agentloop init)"
            )

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def init(cls, root: str | Path, policy_text: str | None = None) -> Loop:
        _executor.init_workspace(Path(root), policy_text)
        return cls(Path(root) / ".loop")

    def propose(
        self,
        *,
        layer: str,
        targets: list[str],
        rationale: str,
        diff: str | None = None,
        folder: str | Path | None = None,
        opaque_ref: str | None = None,
        origin: str | None = None,
        producer: str = "sdk",
        model: str | None = None,
        trigger: str | None = None,
        cs_id: str | None = None,
        supersedes: str | None = None,
    ) -> ChangeSetHandle:
        """Create a ChangeSet from parts and run PROPOSED -> VALIDATED.
        Raises LoopError when validation rejects it (the rejection is journaled)."""
        patch_file = None
        if diff is not None:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".patch", delete=False, encoding="utf-8", newline="\n"
            ) as f:
                f.write(diff)
                patch_file = Path(f.name)
        cs = create_changeset(
            self.workspace.changesets_dir,
            layer=layer,
            targets=targets,
            rationale=rationale,
            producer=producer,
            patch_file=patch_file,
            folder_payload=Path(folder) if folder else None,
            opaque_ref=opaque_ref,
            model=model,
            session=origin,
            trigger=trigger,
            cs_id=cs_id,
            supersedes=supersedes,
        )
        outcome = _executor.propose(self.workspace, cs)
        if not outcome.ok:
            raise LoopError(f"proposal rejected: {outcome.reason}")
        return ChangeSetHandle(self, cs.folder)

    def ingest(self, changeset_dir: str | Path) -> ChangeSetHandle:
        """Ingest a prepared ChangeSet folder (e.g. pulled from a peer) and
        run PROPOSED -> VALIDATED against local policy. Distribution never
        bypasses gates."""
        cs = ingest_changeset(Path(changeset_dir), self.workspace.changesets_dir)
        outcome = _executor.propose(self.workspace, cs)
        if not outcome.ok:
            raise LoopError(f"ingested proposal rejected: {outcome.reason}")
        return ChangeSetHandle(self, cs.folder)

    def gate(self, cs: ChangeSetHandle | str) -> Decision:
        outcome = _executor.gate(self.workspace, self._id_of(cs))
        return Decision(
            approved=outcome.status == _executor.S_GATE_APPROVED,
            queued=outcome.status == _executor.S_QUEUED,
            status=outcome.status,
            reason=outcome.reason,
        )

    def apply(self, cs: ChangeSetHandle | str):
        outcome = _executor.apply_changeset(self.workspace, self._id_of(cs))
        if not outcome.ok:
            raise LoopError(f"apply rejected: {outcome.reason}")
        return outcome

    def rollback(self, cs: ChangeSetHandle | str, actor: str = "sdk/operator"):
        return _executor.rollback(self.workspace, self._id_of(cs), actor)

    def queue_for_review(self, cs: ChangeSetHandle | str) -> str:
        """The L1 path: gate() already queued it; this returns the id for
        hand-off to a human reviewer."""
        return self._id_of(cs)

    def approve(self, cs: ChangeSetHandle | str, actor: str):
        return _executor.approve(self.workspace, self._id_of(cs), actor)

    def log(self, cs: ChangeSetHandle | str | None = None) -> list[dict]:
        entries = self.workspace.journal.entries()
        if cs is None:
            return entries
        cs_id = self._id_of(cs)
        return [e for e in entries if e.get("cs") == cs_id]

    def verify(self) -> list[str]:
        return _executor.verify(self.workspace)

    def sync(self, actor: str = "sdk/sync"):
        """Team-lite: push PROMOTED ChangeSets, pull peers' through the
        configured git-remote registry. Pulled ChangeSets are validated
        against local policy; gate and apply them separately."""
        from agentloop.registry import sync as _sync

        return _sync(self.workspace, actor)

    def promote(self, cs: ChangeSetHandle | str, actor: str = "sdk/operator"):
        return _executor.promote(self.workspace, self._id_of(cs), actor)

    @staticmethod
    def _id_of(cs: ChangeSetHandle | str) -> str:
        return cs if isinstance(cs, str) else cs.id
