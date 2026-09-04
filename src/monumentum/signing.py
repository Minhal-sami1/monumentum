"""Team-lite signing: detached ed25519 signatures over a ChangeSet folder
digest (minisign-style; spec §10.3, invariant I6).

Not full Sigstore/in-toto — that is specified for the full Team profile
and out of v1 scope (GOAL F4).
"""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from monumentum.hashing import sha256_canonical, sha256_file

SIG_FILENAME = "changeset.sig"
# runtime-local folders excluded from the portable digest
_EXCLUDE_TOP = ("snapshot",)


class SigningError(Exception):
    pass


def generate_keypair(out_dir: Path, name: str) -> tuple[Path, Path]:
    """Write <name>.key (private, raw hex) and <name>.pub (public, raw hex)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    key_path = out_dir / f"{name}.key"
    pub_path = out_dir / f"{name}.pub"
    key_path.write_text(private.private_bytes_raw().hex() + "\n", encoding="utf-8", newline="\n")
    pub_path.write_text(
        private.public_key().public_bytes_raw().hex() + "\n", encoding="utf-8", newline="\n"
    )
    return key_path, pub_path


def portable_digest(cs_folder: Path) -> str:
    """Deterministic digest of the portable ChangeSet content: every file
    except runtime-local snapshots and the signature file itself."""
    pairs = []
    for path in sorted(cs_folder.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(cs_folder).as_posix()
        if rel == SIG_FILENAME or rel.split("/", 1)[0] in _EXCLUDE_TOP:
            continue
        pairs.append([rel, sha256_file(path)])
    pairs.sort(key=lambda p: p[0])
    return sha256_canonical(pairs)


def sign_changeset(cs_folder: Path, key_file: Path, signer: str) -> Path:
    key_hex = key_file.read_text(encoding="utf-8").strip()
    private = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key_hex))
    digest = portable_digest(cs_folder)
    signature = private.sign(digest.encode("utf-8"))
    sig = {
        "spec": "monumentum/v0.1",
        "algo": "ed25519",
        "signer": signer,
        "digest": digest,
        "signature": signature.hex(),
    }
    sig_path = cs_folder / SIG_FILENAME
    sig_path.write_text(json.dumps(sig, indent=2) + "\n", encoding="utf-8", newline="\n")
    return sig_path


def verify_changeset(cs_folder: Path, pubkeys_dir: Path) -> str:
    """Verify the detached signature against every trusted public key.
    Returns the signer name. Raises SigningError on any failure."""
    sig_path = cs_folder / SIG_FILENAME
    if not sig_path.is_file():
        raise SigningError(f"unsigned ChangeSet: {cs_folder.name} has no {SIG_FILENAME} (I6)")
    try:
        sig = json.loads(sig_path.read_text(encoding="utf-8"))
        signature = bytes.fromhex(sig["signature"])
        claimed_digest = sig["digest"]
        signer = sig["signer"]
    except (KeyError, ValueError) as exc:
        raise SigningError(f"malformed signature file in {cs_folder.name}: {exc}") from exc

    actual_digest = portable_digest(cs_folder)
    if actual_digest != claimed_digest:
        raise SigningError(
            f"payload tampered: {cs_folder.name} digest {actual_digest} "
            f"does not match signed digest {claimed_digest}"
        )
    if not pubkeys_dir.is_dir():
        raise SigningError(f"no trusted public keys at {pubkeys_dir}")
    for pub_file in sorted(pubkeys_dir.glob("*.pub")):
        pub_hex = pub_file.read_text(encoding="utf-8").strip()
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        try:
            public.verify(signature, actual_digest.encode("utf-8"))
            return signer
        except InvalidSignature:
            continue
    raise SigningError(
        f"bad signature: {cs_folder.name} not signed by any trusted key in {pubkeys_dir}"
    )
