"""Team-lite registry: sync over a plain git remote (spec §10, story C1/C2).

Registry layout in the remote repository:

    changesets/<cs-id>/...    # portable ChangeSet folders (signed)

`sync` pushes locally PROMOTED ChangeSets and pulls peers'. A pulled
ChangeSet enters the local lifecycle at PROPOSED: distribution never
bypasses gates.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agentloop.changeset import load_changeset
from agentloop.executor import propose
from agentloop.schemas import validate_object
from agentloop.signing import SigningError, sign_changeset, verify_changeset
from agentloop.workspace import Workspace

CACHE_DIRNAME = "cache"


class RegistryError(Exception):
    pass


@dataclass
class SyncReport:
    pushed: list[str] = field(default_factory=list)
    pulled: list[str] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)  # (cs_id, reason)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # gate/validate rejections

    @property
    def ok(self) -> bool:
        return not self.refused


def load_registry_config(ws: Workspace) -> dict:
    path = ws.loop / "registry.yaml"
    if not path.is_file():
        raise RegistryError(f"no registry configured ({path} missing)")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = validate_object("registry", config)
    if errors:
        raise RegistryError(f"registry.yaml invalid: {errors[0]}")
    return config


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300
    )
    if proc.returncode != 0:
        raise RegistryError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


def _ensure_cache(ws: Workspace, config: dict) -> Path:
    """Clone or update the registry remote into .loop/cache/registry."""
    cache = ws.loop / CACHE_DIRNAME / "registry"
    url = config["remote"]["url"]
    branch = config["remote"].get("branch", "main")
    # Signed digests cover exact bytes: the cache must never translate
    # line endings, whatever the host git config says.
    no_crlf = ["-c", "core.autocrlf=false", "-c", "core.eol=lf"]
    if not (cache / ".git").is_dir():
        cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(cache, ignore_errors=True)
        try:
            _git([*no_crlf, "clone", "--branch", branch, url, str(cache)], cwd=ws.loop)
        except RegistryError:
            # empty remote: clone it plain and create the branch locally
            shutil.rmtree(cache, ignore_errors=True)
            _git([*no_crlf, "clone", url, str(cache)], cwd=ws.loop)
            _git(["checkout", "-B", branch], cwd=cache)
        _git(["config", "core.autocrlf", "false"], cwd=cache)
        _git(["config", "core.eol", "lf"], cwd=cache)
    else:
        try:
            _git(["fetch", "origin", branch], cwd=cache)
            _git(["reset", "--hard", f"origin/{branch}"], cwd=cache)
        except RegistryError:
            pass  # remote branch does not exist yet (nothing pushed)
    return cache


def _copy_portable(src: Path, dest: Path) -> None:
    """Copy a ChangeSet folder without runtime-local state."""
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("snapshot"))


def sync(ws: Workspace, actor: str) -> SyncReport:
    """Push PROMOTED ChangeSets, pull peers'. Pulled ChangeSets are
    signature-verified (I6) and then validated against LOCAL policy."""
    ws.require()
    config = load_registry_config(ws)
    cache = _ensure_cache(ws, config)
    remote_changesets = cache / "changesets"
    remote_changesets.mkdir(exist_ok=True)
    report = SyncReport()
    state = ws.read_state()

    # -- push: local PROMOTED, not yet in the registry ----------------------
    signing = config.get("signing")
    for cs_id, meta in sorted(state.get("changesets", {}).items()):
        if meta.get("status") != "PROMOTED":
            continue
        dest = remote_changesets / cs_id
        if dest.exists():
            continue
        src = ws.changesets_dir / cs_id
        if signing:
            sign_changeset(src, ws.loop / signing["key_file"], signing["signer"])
        elif config.get("verify", {}).get("require_signatures"):
            raise RegistryError(
                f"registry requires signatures but no signing key is configured; "
                f"cannot push {cs_id}"
            )
        _copy_portable(src, dest)
        _git(["add", "--", f"changesets/{cs_id}"], cwd=cache)
        _git(["-c", "user.name=agentloop", "-c", "user.email=agentloop@local",
              "commit", "-m", f"share {cs_id}"], cwd=cache)
        report.pushed.append(cs_id)
        ws.journal.append("shared", actor=actor, cs=cs_id)
    if report.pushed:
        branch = config["remote"].get("branch", "main")
        _git(["push", "origin", f"HEAD:{branch}"], cwd=cache)
        state = ws.read_state()
        state = ws.update_journal_head(state)
        ws.write_state(state)

    # -- pull: remote ChangeSets unknown locally ----------------------------
    require_sigs = config.get("verify", {}).get("require_signatures", False)
    pubkeys_dir = ws.loop / config.get("verify", {}).get("pubkeys_dir", "pubkeys")
    for remote_dir in sorted(p for p in remote_changesets.iterdir() if p.is_dir()):
        cs_id = remote_dir.name
        if (ws.changesets_dir / cs_id).exists():
            continue
        if require_sigs:
            try:
                verify_changeset(remote_dir, pubkeys_dir)
            except SigningError as exc:
                report.refused.append((cs_id, str(exc)))
                ws.journal.append(
                    "rejected",
                    actor=actor,
                    cs=cs_id if _valid_cs_id(cs_id) else None,
                    decision={"gate": "sync-verify", "reason": str(exc)},
                )
                state = ws.read_state()
                state = ws.update_journal_head(state)
                ws.write_state(state)
                continue
        dest = ws.changesets_dir / cs_id
        _copy_portable(remote_dir, dest)  # signature file stays as provenance
        cs = load_changeset(dest)
        outcome = propose(ws, cs)  # local validation; never bypasses gates
        if outcome.ok:
            report.pulled.append(cs_id)
        else:
            report.rejected.append((cs_id, outcome.reason))
    return report


def _valid_cs_id(cs_id: str) -> bool:
    import re

    return bool(re.fullmatch(r"cs-\d{8}-[a-z0-9]{4,12}", cs_id))
