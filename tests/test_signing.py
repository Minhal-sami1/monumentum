"""Team-lite ed25519 signing tests (C2, invariant I6)."""

import json

import pytest

from monumentum.signing import (
    SigningError,
    generate_keypair,
    portable_digest,
    sign_changeset,
    verify_changeset,
)


@pytest.fixture
def cs_folder(tmp_path):
    folder = tmp_path / "cs-20260831-sig1"
    (folder / "evidence").mkdir(parents=True)
    (folder / "changeset.json").write_text(json.dumps({"id": "cs-20260831-sig1"}),
                                           encoding="utf-8")
    (folder / "payload.patch").write_text("--- a/x\n+++ b/x\n", encoding="utf-8")
    (folder / "evidence" / "ev-001.json").write_text("{}", encoding="utf-8")
    return folder


@pytest.fixture
def keys(tmp_path):
    key, pub = generate_keypair(tmp_path / "keys", "producer-a")
    return key, pub.parent


def test_sign_and_verify_roundtrip(cs_folder, keys):
    key, pub_dir = keys
    sign_changeset(cs_folder, key, "producer-a")
    assert verify_changeset(cs_folder, pub_dir) == "producer-a"


def test_unsigned_refused(cs_folder, keys):
    _, pub_dir = keys
    with pytest.raises(SigningError, match="unsigned"):
        verify_changeset(cs_folder, pub_dir)


def test_tampered_payload_refused(cs_folder, keys):
    key, pub_dir = keys
    sign_changeset(cs_folder, key, "producer-a")
    (cs_folder / "payload.patch").write_text("--- a/x\n+++ b/x\n+backdoor\n", encoding="utf-8")
    with pytest.raises(SigningError, match="tampered"):
        verify_changeset(cs_folder, pub_dir)


def test_untrusted_key_refused(cs_folder, tmp_path):
    evil_key, _ = generate_keypair(tmp_path / "evil", "mallory")
    _, trusted_pub = generate_keypair(tmp_path / "trusted", "producer-a")
    sign_changeset(cs_folder, evil_key, "producer-a")  # claims to be producer-a
    with pytest.raises(SigningError, match="bad signature"):
        verify_changeset(cs_folder, trusted_pub.parent)


def test_snapshot_excluded_from_digest(cs_folder):
    digest_before = portable_digest(cs_folder)
    snapshot = cs_folder / "snapshot"
    snapshot.mkdir()
    (snapshot / "AGENTS.md").write_text("runtime-local state", encoding="utf-8")
    assert portable_digest(cs_folder) == digest_before
