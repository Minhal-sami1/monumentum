"""The reference Executor: lifecycle engine (spec §9).

PROPOSED -> VALIDATED -> GATED -> APPLIED -> OBSERVED -> PROMOTED
                 |          |         |          |
                 +- REJECTED+         +---- ROLLED_BACK <-----+

Every transition is deterministic code and every transition is journaled.
"""

from __future__ import annotations

import datetime as _dt
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agentloop.changeset import ChangeSet, ChangeSetError, load_changeset
from agentloop.diffs import DiffError, apply_patch_set, parse_unified_diff
from agentloop.hashing import sha256_canonical, sha256_file
from agentloop.policy import (
    LoadedPolicy,
    drop_level,
    glob_match,
    load_policy,
    target_allowed,
)
from agentloop.workspace import (
    DEFAULT_POLICY,
    Workspace,
    WorkspaceError,
    ensure_agents_block,
    executor_actor,
)

# ChangeSet status values tracked in state.json.
S_VALIDATED = "VALIDATED"
S_QUEUED = "QUEUED"
S_GATE_APPROVED = "GATE_APPROVED"
S_APPROVED = "APPROVED"
S_APPLIED = "APPLIED"
S_ROLLED_BACK = "ROLLED_BACK"
S_REJECTED = "REJECTED"
S_SUGGESTED = "SUGGESTED"  # L0: journaled, never applies


class ExecutorError(Exception):
    pass


@dataclass
class Outcome:
    ok: bool
    status: str
    reason: str = ""


# --------------------------------------------------------------------------
# init (story A1)
# --------------------------------------------------------------------------


def init_workspace(root: Path, policy_text: str | None = None) -> tuple[Workspace, bool]:
    """Scaffold .loop/ (story A1) and the AGENTS.md managed block (story B2).
    Idempotent: a second init changes nothing and returns created=False."""
    ws = Workspace(root)
    if ws.exists():
        # Idempotent re-init: the AGENTS.md block is written only when its
        # marker is absent; a governed AGENTS.md is never touched here.
        return ws, False
    ws.loop.mkdir(parents=True, exist_ok=True)
    ws.policy_path.write_text(policy_text or DEFAULT_POLICY, encoding="utf-8", newline="\n")
    policy = load_policy(ws.policy_path)
    ws.changesets_dir.mkdir(exist_ok=True)
    ensure_agents_block(ws.root)  # before baseline heads, so the block is covered
    ws.journal.append(
        "genesis",
        actor=executor_actor(),
        decision={"policy_sha256": policy.sha256},
        sig=None,
    )
    state = {
        "spec": "loop/v0.1",
        "effective_levels": {
            layer: policy.declared_level(layer)
            for layer in ("context", "capability", "architecture")
        },
        "changesets": {},
        "heads": _baseline_heads(ws, policy),
        "managed_patterns": _managed_patterns(policy),
        "queue": [],
    }
    state = ws.update_journal_head(state)
    ws.write_state(state)
    return ws, True


def _managed_patterns(policy: LoadedPolicy) -> list[str]:
    """All glob patterns the PreToolUse guard must deny direct edits on."""
    patterns: list[str] = []
    for layer in ("context", "capability", "architecture"):
        patterns.extend(policy.targets_allow(layer))
    patterns.extend(policy.protected())
    return sorted(set(patterns))


def _baseline_heads(ws: Workspace, policy: LoadedPolicy) -> dict[str, str]:
    """Record content hashes of every existing file that the policy governs.
    verify() then detects any ungoverned edit to a managed file (T4)."""
    patterns: list[str] = []
    for layer in ("context", "capability", "architecture"):
        patterns.extend(policy.targets_allow(layer))
    heads: dict[str, str] = {}
    for path in ws.root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ws.root).as_posix()
        if rel.startswith((".loop/", ".git/")):
            continue
        if any(glob_match(rel, pat) for pat in patterns):
            heads[rel] = sha256_file(path)
    return heads


# --------------------------------------------------------------------------
# propose + validate (story A2)
# --------------------------------------------------------------------------


def propose(ws: Workspace, cs: ChangeSet) -> Outcome:
    """Journal the proposal, then validate. The ChangeSet folder must already
    live under .loop/changesets/ (created or ingested by the CLI layer)."""
    ws.require()
    policy = load_policy(ws.policy_path)
    producer = "producer/unknown"
    if isinstance(cs.envelope, dict):
        origin = cs.envelope.get("origin") or {}
        if isinstance(origin, dict) and origin.get("producer"):
            producer = f"producer/{origin['producer']}"
    cs_ref = cs.envelope.get("id") if isinstance(cs.envelope.get("id"), str) else None

    ws.journal.append("proposed", actor=producer, cs=cs_ref, sig=None)

    reason = _validate(cs, policy)
    state = ws.read_state()
    if reason is not None:
        ws.journal.append(
            "rejected",
            actor=executor_actor(),
            cs=cs_ref,
            decision={"gate": "validate", "policy_sha256": policy.sha256, "reason": reason},
            sig=None,
        )
        _set_status(state, cs, S_REJECTED)
        ws.write_state(ws.update_journal_head(state))
        return Outcome(ok=False, status=S_REJECTED, reason=reason)

    _set_status(state, cs, S_VALIDATED)
    ws.write_state(ws.update_journal_head(state))
    return Outcome(ok=True, status=S_VALIDATED)


def _validate(cs: ChangeSet, policy: LoadedPolicy) -> str | None:
    """Schema, allowlist (I4), protected (I1), payload hash. Error or None."""
    errors = cs.schema_errors()
    if errors:
        return f"schema: {errors[0]}"
    for target in cs.targets:
        allowed, why = target_allowed(target, policy.targets_allow(cs.layer), policy.protected())
        if not allowed:
            return why
    return cs.verify_payload_hash()


def _set_status(state: dict, cs: ChangeSet, status: str) -> None:
    changesets = state.setdefault("changesets", {})
    cs_id = cs.envelope.get("id", "<invalid>")
    entry = changesets.setdefault(cs_id, {})
    entry["status"] = status
    entry["layer"] = cs.envelope.get("layer")
    entry["targets"] = cs.envelope.get("targets", [])


# --------------------------------------------------------------------------
# gate (stories A3, A4)
# --------------------------------------------------------------------------


def gate(ws: Workspace, cs_id: str) -> Outcome:
    ws.require()
    policy = load_policy(ws.policy_path)
    state = ws.read_state()
    cs = _load_ws_changeset(ws, cs_id)
    status = _status_of(state, cs_id)
    if status != S_VALIDATED:
        raise ExecutorError(f"{cs_id} is {status}, gate needs VALIDATED")

    level = state.get("effective_levels", {}).get(cs.layer, policy.declared_level(cs.layer))
    gates = policy.gates(cs.layer)

    def reject(reason: str) -> Outcome:
        ws.journal.append(
            "rejected",
            actor=executor_actor(),
            cs=cs_id,
            decision={"gate": "gate", "policy_sha256": policy.sha256, "reason": reason},
            sig=None,
        )
        _set_status(state, cs, S_REJECTED)
        ws.write_state(ws.update_journal_head(state))
        return Outcome(ok=False, status=S_REJECTED, reason=reason)

    # L0: suggest only. Nothing applies, the proposal stays journaled.
    if level == "L0":
        ws.journal.append(
            "gated",
            actor=executor_actor(),
            cs=cs_id,
            decision={"gate": "L0-suggest", "policy_sha256": policy.sha256},
            sig=None,
        )
        _set_status(state, cs, S_SUGGESTED)
        ws.write_state(ws.update_journal_head(state))
        return Outcome(ok=True, status=S_SUGGESTED, reason="L0: suggest only, nothing applies")

    # evidence_required gate: non-empty evidence, artifacts verify.
    if "evidence_required" in gates:
        if not cs.envelope["evidence"]:
            return reject("evidence_required: no evidence attached (D4)")
        problem = cs.verify_evidence_artifacts()
        if problem is not None:
            return reject(f"evidence_required: {problem}")

    # Queue path: L1, or an explicit human_review gate.
    if level == "L1" or "human_review" in gates:
        ws.journal.append(
            "gated",
            actor=executor_actor(),
            cs=cs_id,
            decision={"gate": f"{level}-queue", "policy_sha256": policy.sha256},
            sig=None,
        )
        _set_status(state, cs, S_QUEUED)
        queue = state.setdefault("queue", [])
        if cs_id not in queue:
            queue.append(cs_id)
        ws.write_state(ws.update_journal_head(state))
        return Outcome(ok=True, status=S_QUEUED, reason="queued for human review")

    # Auto path (L2/L3). Invariant I3: at least one independent evidence record.
    try:
        records = [record for record, _ in cs.evidence_records()]
    except ChangeSetError as exc:
        return reject(str(exc))
    if not any(r["grader"] == "independent" for r in records):
        return reject("I3: L2/L3 application requires at least one independent evidence record")

    ws.journal.append(
        "gated",
        actor=executor_actor(),
        cs=cs_id,
        decision={"gate": f"{level}-auto", "policy_sha256": policy.sha256},
        sig=None,
    )
    _set_status(state, cs, S_GATE_APPROVED)
    ws.write_state(ws.update_journal_head(state))
    return Outcome(ok=True, status=S_GATE_APPROVED, reason=f"{level}-auto")


# --------------------------------------------------------------------------
# approve / reject (story A4)
# --------------------------------------------------------------------------


def approve(ws: Workspace, cs_id: str, actor: str) -> Outcome:
    ws.require()
    state = ws.read_state()
    cs = _load_ws_changeset(ws, cs_id)
    if _status_of(state, cs_id) != S_QUEUED:
        raise ExecutorError(f"{cs_id} is {_status_of(state, cs_id)}, approve needs QUEUED")
    _check_reviewer(actor, cs)
    policy = load_policy(ws.policy_path)
    ws.journal.append(
        "approved",
        actor=actor,
        cs=cs_id,
        decision={"gate": "human_review", "policy_sha256": policy.sha256},
        sig=None,
    )
    _set_status(state, cs, S_APPROVED)
    _dequeue(state, cs_id)
    ws.write_state(ws.update_journal_head(state))
    return apply_changeset(ws, cs_id)


def reject_changeset(ws: Workspace, cs_id: str, actor: str, reason: str) -> Outcome:
    ws.require()
    state = ws.read_state()
    cs = _load_ws_changeset(ws, cs_id)
    if _status_of(state, cs_id) != S_QUEUED:
        raise ExecutorError(f"{cs_id} is {_status_of(state, cs_id)}, reject needs QUEUED")
    _check_reviewer(actor, cs)
    policy = load_policy(ws.policy_path)
    ws.journal.append(
        "rejected",
        actor=actor,
        cs=cs_id,
        decision={"gate": "human_review", "policy_sha256": policy.sha256, "reason": reason},
        sig=None,
    )
    _set_status(state, cs, S_REJECTED)
    _dequeue(state, cs_id)
    ws.write_state(ws.update_journal_head(state))
    return Outcome(ok=True, status=S_REJECTED, reason=reason)


def _check_reviewer(actor: str, cs: ChangeSet) -> None:
    if not actor.startswith(("reviewer/", "human/")):
        raise ExecutorError("approval actor must be reviewer/<id> or human/<id>")
    producer = cs.envelope.get("origin", {}).get("producer", "")
    if actor.split("/", 1)[1] == producer:
        raise ExecutorError("the producer identity cannot review its own ChangeSet")


def _dequeue(state: dict, cs_id: str) -> None:
    queue = state.setdefault("queue", [])
    if cs_id in queue:
        queue.remove(cs_id)


# --------------------------------------------------------------------------
# apply (story A3) + reproducible_check
# --------------------------------------------------------------------------


def apply_changeset(ws: Workspace, cs_id: str) -> Outcome:
    ws.require()
    policy = load_policy(ws.policy_path)
    state = ws.read_state()
    cs = _load_ws_changeset(ws, cs_id)
    status = _status_of(state, cs_id)
    if status not in (S_GATE_APPROVED, S_APPROVED):
        raise ExecutorError(f"{cs_id} is {status}, apply needs GATE_APPROVED or APPROVED")
    if cs.payload["type"] == "opaque":
        return _journal_opaque(ws, state, cs, policy)

    before = {t: ws.target_hash(t) for t in cs.targets}
    snapshot_dir = cs.folder / "snapshot"
    _snapshot(ws, cs.targets, snapshot_dir)

    try:
        _apply_payload(ws, cs)
    except (DiffError, ExecutorError, WorkspaceError, OSError) as exc:
        _restore(ws, cs.targets, snapshot_dir)
        return _reject_at_apply(ws, state, cs, policy, f"apply failed: {exc}")

    # reproducible_check gate runs against the applied state; failure reverts.
    if "reproducible_check" in policy.gates(cs.layer):
        problem = _reproducible_check(ws, cs)
        if problem is not None:
            _restore(ws, cs.targets, snapshot_dir)
            return _reject_at_apply(ws, state, cs, policy, f"reproducible_check: {problem}")

    after = {t: ws.target_hash(t) for t in cs.targets}
    commit = _git_commit(ws, cs.targets, f"agentloop: apply {cs_id}")
    ws.journal.append(
        "applied",
        actor=executor_actor(),
        cs=cs_id,
        decision={"gate": _gate_label(state, cs, policy), "policy_sha256": policy.sha256},
        target_state={
            "before": _combined_hash(before),
            "after": _combined_hash(after),
            "commit": commit,
        },
        sig=None,
    )
    _set_status(state, cs, S_APPLIED)
    entry = state["changesets"][cs_id]
    entry["before"] = before
    entry["after"] = after
    heads = state.setdefault("heads", {})
    for target, digest in after.items():
        if digest is None:
            heads.pop(target, None)
        else:
            heads[target] = digest
    ws.write_state(ws.update_journal_head(state))
    return Outcome(ok=True, status=S_APPLIED)


def _gate_label(state: dict, cs: ChangeSet, policy: LoadedPolicy) -> str:
    if _status_of(state, cs.id) == S_APPROVED:
        return "human_review"
    level = state.get("effective_levels", {}).get(cs.layer, policy.declared_level(cs.layer))
    return f"{level}-auto"


def _journal_opaque(ws: Workspace, state: dict, cs: ChangeSet, policy: LoadedPolicy) -> Outcome:
    """Opaque payloads are journaled, never applied (design D2)."""
    ws.journal.append(
        "weight_update",
        actor=executor_actor(),
        cs=cs.id,
        decision={"gate": _gate_label(state, cs, policy), "policy_sha256": policy.sha256},
        ext={"weight_update": {"payload_ref": cs.payload["ref"]}},
        sig=None,
    )
    _set_status(state, cs, S_APPLIED)
    ws.write_state(ws.update_journal_head(state))
    return Outcome(ok=True, status=S_APPLIED, reason="opaque payload journaled, not applied")


def _reject_at_apply(
    ws: Workspace, state: dict, cs: ChangeSet, policy: LoadedPolicy, reason: str
) -> Outcome:
    ws.journal.append(
        "rejected",
        actor=executor_actor(),
        cs=cs.id,
        decision={"gate": "apply", "policy_sha256": policy.sha256, "reason": reason},
        sig=None,
    )
    _set_status(state, cs, S_REJECTED)
    ws.write_state(ws.update_journal_head(state))
    return Outcome(ok=False, status=S_REJECTED, reason=reason)


def _snapshot(ws: Workspace, targets: list[str], snapshot_dir: Path) -> None:
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True)
    manifest = {}
    for target in targets:
        src = ws.target_abspath(target)
        if src.is_file():
            dest = snapshot_dir / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            manifest[target] = sha256_file(src)
        else:
            manifest[target] = None
    (snapshot_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def _restore(ws: Workspace, targets: list[str], snapshot_dir: Path) -> dict[str, str | None]:
    manifest = json.loads((snapshot_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    restored: dict[str, str | None] = {}
    for target in targets:
        dest = ws.target_abspath(target)
        prior = manifest.get(target)
        if prior is None:
            if dest.is_file():
                dest.unlink()
            restored[target] = None
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshot_dir / target, dest)
            restored[target] = sha256_file(dest)
            if restored[target] != prior:
                raise ExecutorError(f"restore hash mismatch for {target}")
    return restored


def _apply_payload(ws: Workspace, cs: ChangeSet) -> None:
    if cs.payload["type"] == "diff":
        diff_text = cs.payload_path().read_text(encoding="utf-8")
        patches = parse_unified_diff(diff_text)
        patch_targets = {p.target for p in patches}
        if patch_targets != set(cs.targets):
            raise ExecutorError(
                f"payload touches {sorted(patch_targets)} "
                f"but envelope declares {sorted(cs.targets)}"
            )
        current: dict[str, str | None] = {}
        for patch in patches:
            for path in (patch.old_path, patch.new_path):
                if path is not None and path not in current:
                    abspath = ws.target_abspath(path)
                    current[path] = (
                        abspath.read_text(encoding="utf-8") if abspath.is_file() else None
                    )
        results = apply_patch_set(patches, current)
        for target, content in results.items():
            dest = ws.target_abspath(target)
            if content is None:
                if dest.is_file():
                    dest.unlink()
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8", newline="\n")
    else:  # folder payload mirrors workspace-relative target paths
        payload_dir = cs.payload_path()
        for target in cs.targets:
            src = payload_dir / target
            if not src.is_file():
                raise ExecutorError(f"folder payload missing target file: {target}")
            dest = ws.target_abspath(target)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)


def _reproducible_check(ws: Workspace, cs: ChangeSet) -> str | None:
    """Re-run the recorded check command from command-transcript evidence.
    The recorded post-change outcome (exit 0) is REQUIRED. Error or None."""
    transcripts = []
    for record, path in cs.evidence_records():
        if record["format"] == "command-transcript":
            transcripts.append((record, path))
    if not transcripts:
        return None  # nothing to reproduce; artifact integrity was already gated
    for record, path in transcripts:
        artifact_path = path.parent / record["artifact"]["path"]
        try:
            transcript = json.loads(artifact_path.read_text(encoding="utf-8"))
            check_cmd = transcript["check_cmd"]
        except Exception:
            return (
                f"transcript {record['id']} is not machine-checkable: "
                "expected JSON with a check_cmd field"
            )
        try:
            proc = subprocess.run(
                check_cmd, shell=True, cwd=ws.root, capture_output=True, text=True, timeout=300
            )
        except subprocess.TimeoutExpired:
            return f"check command timed out after 300s: {check_cmd}"
        if proc.returncode != 0:
            return (
                f"check command failed after apply (exit {proc.returncode}): {check_cmd}"
            )
    return None


def _combined_hash(hashes: dict[str, str | None]) -> str:
    """One deterministic hash over the whole target set (sorted pairs)."""
    return sha256_canonical(sorted(hashes.items()))


def _git_commit(ws: Workspace, targets: list[str], message: str) -> str | None:
    if not (ws.root / ".git").exists():
        return None
    try:
        paths = [t for t in targets] + [".loop"]
        subprocess.run(
            ["git", "-C", str(ws.root), "add", "--", *paths],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(ws.root), "commit", "-m", message, "--allow-empty"],
            check=True, capture_output=True, text=True,
        )
        proc = subprocess.run(
            ["git", "-C", str(ws.root), "rev-parse", "--short", "HEAD"],
            check=True, capture_output=True, text=True,
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError:
        return None


# --------------------------------------------------------------------------
# promote (Team profile: eligible for the registry)
# --------------------------------------------------------------------------

S_PROMOTED = "PROMOTED"


def promote(ws: Workspace, cs_id: str, actor: str) -> Outcome:
    ws.require()
    state = ws.read_state()
    cs = _load_ws_changeset(ws, cs_id)
    if _status_of(state, cs_id) != S_APPLIED:
        raise ExecutorError(f"{cs_id} is {_status_of(state, cs_id)}, promote needs APPLIED")
    ws.journal.append("promoted", actor=actor, cs=cs_id)
    _set_status(state, cs, S_PROMOTED)
    ws.write_state(ws.update_journal_head(state))
    return Outcome(ok=True, status=S_PROMOTED)


# --------------------------------------------------------------------------
# rollback + de-escalation (story A5)
# --------------------------------------------------------------------------


def rollback(ws: Workspace, cs_id: str, actor: str) -> Outcome:
    ws.require()
    policy = load_policy(ws.policy_path)
    state = ws.read_state()
    cs = _load_ws_changeset(ws, cs_id)
    if _status_of(state, cs_id) not in (S_APPLIED, S_PROMOTED):
        raise ExecutorError(
            f"{cs_id} is {_status_of(state, cs_id)}, rollback needs APPLIED or PROMOTED"
        )
    if cs.payload["type"] == "opaque":
        raise ExecutorError("opaque entries are journal-only; nothing to roll back")

    snapshot_dir = cs.folder / "snapshot"
    if not snapshot_dir.is_dir():
        raise ExecutorError(f"snapshot missing for {cs_id}; cannot roll back")
    applied_after = {t: ws.target_hash(t) for t in cs.targets}
    restored = _restore(ws, cs.targets, snapshot_dir)
    commit = _git_commit(ws, cs.targets, f"agentloop: rollback {cs_id}")
    ws.journal.append(
        "rolled_back",
        actor=actor,
        cs=cs_id,
        target_state={
            "before": _combined_hash(applied_after),
            "after": _combined_hash(restored),
            "commit": commit,
        },
        sig=None,
    )
    _set_status(state, cs, S_ROLLED_BACK)
    heads = state.setdefault("heads", {})
    for target, digest in restored.items():
        if digest is None:
            heads.pop(target, None)
        else:
            heads[target] = digest
    ws.write_state(ws.update_journal_head(state))
    _maybe_de_escalate(ws, cs.layer, policy)
    return Outcome(ok=True, status=S_ROLLED_BACK)


def _maybe_de_escalate(ws: Workspace, layer: str, policy: LoadedPolicy) -> None:
    rule = policy.de_escalation()
    if not rule:
        return
    state = ws.read_state()
    window_start = _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=rule["window_days"])
    count = 0
    for entry in ws.journal.entries():
        if entry["event"] != "rolled_back":
            continue
        cs_meta = state.get("changesets", {}).get(entry.get("cs", ""), {})
        if cs_meta.get("layer") != layer:
            continue
        ts = _dt.datetime.strptime(entry["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.UTC)
        if ts >= window_start:
            count += 1
    if count < rule["on_rollbacks"]:
        return
    current = state["effective_levels"][layer]
    lowered = drop_level(current, rule["drop"])
    if lowered == current:
        return
    ws.journal.append(
        "policy_changed",
        actor=executor_actor(),
        decision={
            "gate": "de_escalation",
            "policy_sha256": policy.sha256,
            "reason": (
                f"{count} rollbacks of {layer} changes in {rule['window_days']} days: "
                f"{layer} drops {current} -> {lowered}"
            ),
        },
        sig=None,
    )
    state["effective_levels"][layer] = lowered
    ws.write_state(ws.update_journal_head(state))


# --------------------------------------------------------------------------
# verify (story A6 + universal backstop)
# --------------------------------------------------------------------------


def verify(ws: Workspace) -> list[str]:
    """Returns a list of problems; empty means the workspace verifies."""
    problems: list[str] = []
    if not ws.exists():
        return [f"no .loop workspace at {ws.root}"]
    break_ = ws.journal.verify_chain()
    if break_ is not None:
        problems.append(f"journal: {break_.reason} (seq {break_.seq})")
    state = ws.read_state()
    if state:
        last = ws.journal.last_line()
        from agentloop.hashing import sha256_bytes

        head = sha256_bytes(last) if last else None
        if state.get("journal_head") != head:
            problems.append(
                "journal head mismatch: state.json does not match the newest journal line "
                "(tail tampering or missing entries)"
            )
        for target, expected in sorted(state.get("heads", {}).items()):
            actual = ws.target_hash(target)
            if actual != expected:
                problems.append(
                    f"managed file changed outside the loop: {target} "
                    f"(expected {expected}, found {actual})"
                )
    try:
        load_policy(ws.policy_path)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"policy: {exc}")
    return problems


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _load_ws_changeset(ws: Workspace, cs_id: str) -> ChangeSet:
    folder = ws.changesets_dir / cs_id
    if not folder.is_dir():
        raise ExecutorError(f"changeset not found in workspace: {cs_id}")
    return load_changeset(folder)


def _status_of(state: dict, cs_id: str) -> str:
    entry = state.get("changesets", {}).get(cs_id)
    if entry is None:
        raise ExecutorError(f"changeset unknown to state: {cs_id}")
    return entry["status"]


def workspace_for(path: Path) -> Workspace:
    ws = Workspace(path)
    if not ws.exists():
        raise WorkspaceError(f"no .loop workspace at {ws.root}")
    return ws
