"""ChangeSet folder I/O (spec §5) and evidence loading (spec §6)."""

from __future__ import annotations

import datetime as _dt
import json
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

from monumentum.hashing import sha256_file, sha256_folder
from monumentum.schemas import validate_object


class ChangeSetError(Exception):
    pass


def new_changeset_id(now: _dt.datetime | None = None) -> str:
    now = now or _dt.datetime.now(_dt.UTC)
    return f"cs-{now:%Y%m%d}-{secrets.token_hex(4)}"


@dataclass
class ChangeSet:
    folder: Path
    envelope: dict

    @property
    def id(self) -> str:
        return self.envelope["id"]

    @property
    def layer(self) -> str:
        return self.envelope["layer"]

    @property
    def targets(self) -> list[str]:
        return self.envelope["targets"]

    @property
    def payload(self) -> dict:
        return self.envelope["payload"]

    def payload_path(self) -> Path | None:
        if "path" not in self.payload:
            return None
        return self.folder / self.payload["path"]

    def save_envelope(self) -> None:
        self.folder.joinpath("changeset.json").write_text(
            json.dumps(self.envelope, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    # -- validation pieces (schema + payload integrity) --------------------

    def schema_errors(self) -> list[str]:
        return validate_object("changeset", self.envelope)

    def verify_payload_hash(self) -> str | None:
        """Returns an error string, or None when the payload hash checks out."""
        ptype = self.payload["type"]
        if ptype == "opaque":
            return None
        path = self.payload_path()
        if path is None:
            return "payload path missing"
        if ptype == "diff":
            if not path.is_file():
                return f"payload file not found: {self.payload['path']}"
            actual = sha256_file(path)
        else:  # folder
            if not path.is_dir():
                return f"payload folder not found: {self.payload['path']}"
            actual = sha256_folder(path)
        if actual != self.payload["sha256"]:
            return f"payload hash mismatch: envelope says {self.payload['sha256']}, actual {actual}"
        return None

    # -- evidence -----------------------------------------------------------

    def evidence_records(self) -> list[tuple[dict, Path]]:
        """Load all evidence records. Raises ChangeSetError on structural problems."""
        out = []
        for rel in self.envelope["evidence"]:
            path = self.folder / rel
            if not path.is_file():
                raise ChangeSetError(f"evidence record not found: {rel}")
            record = json.loads(path.read_text(encoding="utf-8"))
            errors = validate_object("evidence", record)
            if errors:
                raise ChangeSetError(f"evidence {rel} invalid: {errors[0]}")
            out.append((record, path))
        return out

    def verify_evidence_artifacts(self) -> str | None:
        """Check every evidence artifact hash. Error string or None."""
        try:
            records = self.evidence_records()
        except ChangeSetError as exc:
            return str(exc)
        for record, path in records:
            artifact = record.get("artifact")
            if artifact is None:
                continue
            artifact_path = path.parent / artifact["path"]
            if not artifact_path.is_file():
                return f"evidence artifact not found: {artifact['path']} (record {record['id']})"
            actual = sha256_file(artifact_path)
            if actual != artifact["sha256"]:
                return (
                    f"evidence artifact hash mismatch for {record['id']}: "
                    f"record says {artifact['sha256']}, actual {actual}"
                )
        return None


def load_changeset(folder: Path) -> ChangeSet:
    envelope_path = folder / "changeset.json"
    if not envelope_path.is_file():
        raise ChangeSetError(f"changeset.json not found in {folder}")
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    return ChangeSet(folder=folder, envelope=envelope)


def create_changeset(
    dest_parent: Path,
    *,
    layer: str,
    targets: list[str],
    rationale: str,
    producer: str,
    patch_file: Path | None = None,
    folder_payload: Path | None = None,
    opaque_ref: str | None = None,
    model: str | None = None,
    session: str | None = None,
    trigger: str | None = None,
    cs_id: str | None = None,
    supersedes: str | None = None,
) -> ChangeSet:
    """Create a ChangeSet folder from parts. Exactly one payload source."""
    sources = [s for s in (patch_file, folder_payload, opaque_ref) if s is not None]
    if len(sources) != 1:
        raise ChangeSetError("exactly one of patch file, folder payload, or opaque ref")
    cs_id = cs_id or new_changeset_id()
    folder = dest_parent / cs_id
    if folder.exists():
        raise ChangeSetError(f"changeset folder already exists: {folder}")
    folder.mkdir(parents=True)
    (folder / "evidence").mkdir()

    if patch_file is not None:
        dest = folder / "payload.patch"
        shutil.copyfile(patch_file, dest)
        payload = {"type": "diff", "path": "payload.patch", "sha256": sha256_file(dest)}
    elif folder_payload is not None:
        dest = folder / "payload"
        shutil.copytree(folder_payload, dest)
        payload = {"type": "folder", "path": "payload/", "sha256": sha256_folder(dest)}
    else:
        payload = {"type": "opaque", "ref": opaque_ref}

    envelope = {
        "spec": "monumentum/v0.1",
        "id": cs_id,
        "layer": layer,
        "targets": targets,
        "payload": payload,
        "origin": {"producer": producer, "model": model, "session": session, "trigger": trigger},
        "rationale": rationale,
        "evidence": [],
        "provenance": None,
        "supersedes": supersedes,
        "created": _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    cs = ChangeSet(folder=folder, envelope=envelope)
    cs.save_envelope()
    return cs


def ingest_changeset(src_dir: Path, dest_parent: Path) -> ChangeSet:
    """Copy a prepared ChangeSet folder into the workspace changesets dir."""
    src = load_changeset(src_dir)
    dest = dest_parent / src.id
    if dest.exists():
        raise ChangeSetError(f"changeset {src.id} already exists in workspace")
    dest_parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_dir, dest)
    return load_changeset(dest)


def attach_evidence(
    cs: ChangeSet, record_file: Path, artifact_file: Path | None = None, *, fill_hash: bool = True
) -> dict:
    """Copy an evidence record (+ optional artifact) into the ChangeSet and
    register it in the envelope. When fill_hash is set and an artifact is
    given, the record's artifact hash is computed from the file."""
    record = json.loads(record_file.read_text(encoding="utf-8"))
    evidence_dir = cs.folder / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    if artifact_file is not None:
        artifact_dest = evidence_dir / artifact_file.name
        shutil.copyfile(artifact_file, artifact_dest)
        if fill_hash:
            record["artifact"] = {
                "path": artifact_file.name,
                "sha256": sha256_file(artifact_dest),
            }
    errors = validate_object("evidence", record)
    if errors:
        raise ChangeSetError(f"evidence record invalid: {errors[0]}")
    rel = f"evidence/{record['id']}.json"
    (cs.folder / rel).write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if rel not in cs.envelope["evidence"]:
        cs.envelope["evidence"].append(rel)
        cs.save_envelope()
    return record
