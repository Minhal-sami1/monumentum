"""Content hashing. One format everywhere: sha256:<64 lowercase hex> (DEC-002)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PREFIX = "sha256:"


def sha256_bytes(data: bytes) -> str:
    return PREFIX + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return PREFIX + h.hexdigest()


def canonical_json(obj: object) -> str:
    """Canonical serialization used for journal lines and folder digests.

    Compact separators, sorted keys, UTF-8 (no ASCII escaping). The exact
    bytes of this serialization are what the hash chain covers.
    """
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sha256_canonical(obj: object) -> str:
    return sha256_bytes(canonical_json(obj).encode("utf-8"))


def sha256_folder(root: Path) -> str:
    """Deterministic folder digest: canonical JSON of sorted [relpath, filehash]
    pairs, hashed. Relpaths use POSIX separators. Empty dirs are ignored.
    """
    pairs = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            pairs.append([rel, sha256_file(path)])
    pairs.sort(key=lambda p: p[0])
    return sha256_canonical(pairs)
