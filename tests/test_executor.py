"""Executor lifecycle tests: stories A1-A6."""

import json
import shutil
import sys
from pathlib import Path

import pytest

from monumentum.changeset import attach_evidence, create_changeset, load_changeset
from monumentum.executor import (
    ExecutorError,
    apply_changeset,
    approve,
    gate,
    init_workspace,
    propose,
    reject_changeset,
    rollback,
    verify,
)
from monumentum.workspace import Workspace

AGENTS_BEFORE = "# Agent notes\n\nUse npm install to set up.\n"
AGENTS_AFTER = "# Agent notes\n\nUse pnpm install to set up.\n"

PATCH = """\
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up.
"""

PY = Path(sys.executable).as_posix()
CHECK_OK = (
    f'"{PY}" -c "import sys; '
    "sys.exit(0 if 'pnpm' in open('AGENTS.md', encoding='utf-8').read() else 1)\""
)


@pytest.fixture
def ws(tmp_path) -> Workspace:
    (tmp_path / "AGENTS.md").write_text(AGENTS_BEFORE, encoding="utf-8", newline="\n")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "helper.py").write_text("print('v1')\n", encoding="utf-8", newline="\n")
    workspace, created = init_workspace(tmp_path)
    assert created
    return workspace


def _write_patch(ws: Workspace, text: str = PATCH) -> Path:
    path = ws.root / "fix.patch"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _transcript(ws: Workspace, check_cmd: str = CHECK_OK) -> Path:
    path = ws.root / "transcript.json"
    path.write_text(
        json.dumps({"check_cmd": check_cmd, "runs": [
            {"phase": "before", "exit_code": 1}, {"phase": "after", "exit_code": 0},
        ]}),
        encoding="utf-8",
    )
    return path


def _record(ws: Workspace, grader: str = "independent") -> Path:
    path = ws.root / "ev.json"
    path.write_text(
        json.dumps({
            "id": "ev-001", "kind": "eval", "grader": grader,
            "format": "command-transcript",
            "summary": {"metric": "task_pass", "before": 0, "after": 1, "n": 1},
        }),
        encoding="utf-8",
    )
    return path


def _propose_context(ws: Workspace, cs_id: str = "cs-20260830-t001"):
    cs = create_changeset(
        ws.changesets_dir, layer="context", targets=["AGENTS.md"],
        rationale="Repo uses pnpm.", producer="claude-code",
        patch_file=_write_patch(ws), cs_id=cs_id,
    )
    outcome = propose(ws, cs)
    return cs, outcome


def _with_evidence(ws: Workspace, cs, grader: str = "independent", check_cmd: str = CHECK_OK):
    attach_evidence(cs, _record(ws, grader), _transcript(ws, check_cmd))
    return load_changeset(cs.folder)


# -- A1: init ---------------------------------------------------------------


def test_init_scaffold(ws):
    assert ws.policy_path.is_file()
    entries = ws.journal.entries()
    assert entries[0]["event"] == "genesis"
    state = ws.read_state()
    assert state["effective_levels"] == {"context": "L2", "capability": "L1", "architecture": "L1"}
    assert "AGENTS.md" in state["heads"]  # baseline head for managed file
    assert "tools/helper.py" in state["heads"]
    assert verify(ws) == []


def test_double_init_idempotent_one_block(ws):
    agents_before = (ws.root / "AGENTS.md").read_text(encoding="utf-8")
    _, created = init_workspace(ws.root)
    assert not created
    agents_after = (ws.root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_after == agents_before
    assert agents_after.count("<!-- monumentum:managed:begin -->") == 1
    assert verify(ws) == []


# -- A2: propose + validate ---------------------------------------------------


def test_propose_valid(ws):
    _, outcome = _propose_context(ws)
    assert outcome.ok and outcome.status == "VALIDATED"
    events = [e["event"] for e in ws.journal.entries()]
    assert events == ["genesis", "proposed"]


def test_propose_records_supersedes(ws):
    cs = create_changeset(
        ws.changesets_dir, layer="context", targets=["AGENTS.md"],
        rationale="replaces an earlier lesson", producer="claude-code",
        patch_file=_write_patch(ws), cs_id="cs-20260830-t003",
        supersedes="cs-20260830-t001",
    )
    assert propose(ws, cs).ok
    assert load_changeset(cs.folder).envelope["supersedes"] == "cs-20260830-t001"


def test_propose_out_of_allowlist_rejected(ws):
    cs = create_changeset(
        ws.changesets_dir, layer="context", targets=["src/main.py"],
        rationale="x", producer="claude-code", patch_file=_write_patch(ws),
    )
    outcome = propose(ws, cs)
    assert not outcome.ok and "I4" in outcome.reason
    assert ws.journal.entries()[-1]["event"] == "rejected"


def test_propose_payload_hash_mismatch_rejected(ws):
    cs, _ = _propose_context(ws)
    cs.envelope["payload"]["sha256"] = "sha256:" + "0" * 64
    cs.save_envelope()
    cs2 = load_changeset(cs.folder)
    # re-validate through a fresh propose of a copy
    dest = ws.changesets_dir / "cs-20260830-t002"
    shutil.copytree(cs2.folder, dest)
    cs3 = load_changeset(dest)
    cs3.envelope["id"] = "cs-20260830-t002"
    cs3.save_envelope()
    outcome = propose(ws, cs3)
    assert not outcome.ok and "hash mismatch" in outcome.reason


# -- A3: gate + apply at L2 ----------------------------------------------------


def test_gate_no_evidence_rejected(ws):
    cs, _ = _propose_context(ws)
    outcome = gate(ws, cs.id)
    assert not outcome.ok and "evidence_required" in outcome.reason


def test_gate_self_evidence_rejected_i3(ws):
    cs, _ = _propose_context(ws)
    _with_evidence(ws, cs, grader="self")
    outcome = gate(ws, cs.id)
    assert not outcome.ok and "I3" in outcome.reason


def test_l2_auto_apply_with_independent_evidence(ws):
    cs, _ = _propose_context(ws)
    _with_evidence(ws, cs)
    assert gate(ws, cs.id).status == "GATE_APPROVED"
    outcome = apply_changeset(ws, cs.id)
    assert outcome.ok and outcome.status == "APPLIED"
    assert (ws.root / "AGENTS.md").read_text(encoding="utf-8").startswith(AGENTS_AFTER)
    events = [e["event"] for e in ws.journal.entries()]
    assert events == ["genesis", "proposed", "gated", "applied"]
    assert verify(ws) == []


def test_reproducible_check_failure_reverts(ws):
    cs, _ = _propose_context(ws)
    fail_cmd = f'"{PY}" -c "import sys; sys.exit(1)"'
    _with_evidence(ws, cs, check_cmd=fail_cmd)
    assert gate(ws, cs.id).status == "GATE_APPROVED"
    outcome = apply_changeset(ws, cs.id)
    assert not outcome.ok and "reproducible_check" in outcome.reason
    assert (ws.root / "AGENTS.md").read_text(encoding="utf-8").startswith(AGENTS_BEFORE)
    assert ws.journal.entries()[-1]["event"] == "rejected"
    assert verify(ws) == []


# -- A4: L1 queue --------------------------------------------------------------


def _propose_capability(ws: Workspace, cs_id: str = "cs-20260830-t010"):
    patch = ws.root / "cap.patch"
    patch.write_text(
        "--- a/tools/helper.py\n+++ b/tools/helper.py\n@@ -1 +1 @@\n"
        "-print('v1')\n+print('v2')\n",
        encoding="utf-8", newline="\n",
    )
    cs = create_changeset(
        ws.changesets_dir, layer="capability", targets=["tools/helper.py"],
        rationale="fix helper", producer="claude-code", patch_file=patch, cs_id=cs_id,
    )
    propose(ws, cs)
    record = ws.root / "ev-h.json"
    record.write_text(
        json.dumps({
            "id": "ev-h1", "kind": "human", "grader": "independent",
            "format": "human-feedback", "summary": {"metric": "works"},
        }),
        encoding="utf-8",
    )
    attach_evidence(load_changeset(cs.folder), record)
    return load_changeset(cs.folder)


def test_l1_queue_and_approve(ws):
    cs = _propose_capability(ws)
    outcome = gate(ws, cs.id)
    assert outcome.status == "QUEUED"
    # target untouched while queued
    assert (ws.root / "tools" / "helper.py").read_text(encoding="utf-8") == "print('v1')\n"
    outcome = approve(ws, cs.id, "reviewer/minhal")
    assert outcome.ok and outcome.status == "APPLIED"
    assert (ws.root / "tools" / "helper.py").read_text(encoding="utf-8") == "print('v2')\n"
    events = [e["event"] for e in ws.journal.entries()]
    assert events[-2:] == ["approved", "applied"]


def test_l1_reject_never_applies(ws):
    cs = _propose_capability(ws)
    gate(ws, cs.id)
    outcome = reject_changeset(ws, cs.id, "reviewer/minhal", "not convinced")
    assert outcome.status == "REJECTED"
    assert (ws.root / "tools" / "helper.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert ws.journal.entries()[-1]["event"] == "rejected"


def test_producer_cannot_self_approve(ws):
    cs = _propose_capability(ws)
    gate(ws, cs.id)
    with pytest.raises(ExecutorError, match="cannot review its own"):
        approve(ws, cs.id, "reviewer/claude-code")


def test_apply_requires_approval(ws):
    cs = _propose_capability(ws)
    gate(ws, cs.id)
    with pytest.raises(ExecutorError, match="apply needs"):
        apply_changeset(ws, cs.id)


# -- A5: rollback + de-escalation ----------------------------------------------


def _apply_context(ws: Workspace, cs_id: str) -> None:
    cs = create_changeset(
        ws.changesets_dir, layer="context", targets=["AGENTS.md"],
        rationale="pnpm", producer="claude-code",
        patch_file=_write_patch(ws), cs_id=cs_id,
    )
    propose(ws, cs)
    _with_evidence(ws, load_changeset(cs.folder))
    gate(ws, cs_id)
    assert apply_changeset(ws, cs_id).ok


def test_rollback_restores_exact_hashes(ws):
    before_hash = ws.target_hash("AGENTS.md")
    _apply_context(ws, "cs-20260830-t020")
    assert ws.target_hash("AGENTS.md") != before_hash
    outcome = rollback(ws, "cs-20260830-t020", "human/minhal")
    assert outcome.ok
    assert ws.target_hash("AGENTS.md") == before_hash
    assert verify(ws) == []


def test_two_rollbacks_de_escalate(ws):
    _apply_context(ws, "cs-20260830-t021")
    rollback(ws, "cs-20260830-t021", "human/minhal")
    _apply_context(ws, "cs-20260830-t022")
    rollback(ws, "cs-20260830-t022", "human/minhal")
    state = ws.read_state()
    assert state["effective_levels"]["context"] == "L1"
    events = [e["event"] for e in ws.journal.entries()]
    assert events[-1] == "policy_changed"
    entry = ws.journal.entries()[-1]
    assert "L2 -> L1" in entry["decision"]["reason"]
    assert verify(ws) == []


# -- A6 + backstop: verify -------------------------------------------------------


def test_verify_detects_journal_tamper(ws):
    _apply_context(ws, "cs-20260830-t030")
    path = ws.journal.files()[0]
    data = path.read_bytes().replace(b"claude-code", b"claude-evil")
    path.write_bytes(data)
    problems = verify(ws)
    assert problems and any("journal" in p for p in problems)


def test_verify_detects_hand_edit_of_managed_file(ws):
    (ws.root / "AGENTS.md").write_text("hand-edited\n", encoding="utf-8")
    problems = verify(ws)
    assert problems and any("outside the loop" in p for p in problems)


def test_verify_detects_tail_truncation(ws):
    _apply_context(ws, "cs-20260830-t031")
    path = ws.journal.files()[0]
    lines = [ln for ln in path.read_bytes().split(b"\n") if ln.strip()]
    path.write_bytes(b"\n".join(lines[:-1]) + b"\n")
    problems = verify(ws)
    assert problems and any("head mismatch" in p for p in problems)
