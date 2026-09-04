"""Schema-level unit tests: compile, golden corpus, and edge cases."""

import copy
import json
from pathlib import Path

import pytest

from monumentum.schemas import OBJECT_TYPES, get_validator, load_instance, validate_object

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "conformance" / "golden"


def _golden_files(expectation: str) -> list[tuple[str, Path]]:
    out = []
    for object_type in sorted(OBJECT_TYPES):
        sub = GOLDEN / object_type / expectation
        for path in sorted(sub.rglob("*")):
            if path.is_file():
                out.append((object_type, path))
    return out


@pytest.mark.parametrize("object_type", sorted(OBJECT_TYPES))
def test_schema_compiles(object_type):
    get_validator(object_type)


@pytest.mark.parametrize(
    ("object_type", "path"),
    _golden_files("valid"),
    ids=lambda v: v.name if isinstance(v, Path) else v,
)
def test_golden_valid_passes(object_type, path):
    errors = validate_object(object_type, load_instance(path))
    assert errors == [], f"{path.name} must validate: {errors}"


@pytest.mark.parametrize(
    ("object_type", "path"),
    _golden_files("invalid"),
    ids=lambda v: v.name if isinstance(v, Path) else v,
)
def test_golden_invalid_fails(object_type, path):
    errors = validate_object(object_type, load_instance(path))
    assert errors, f"{path.name} is a REQUIRED-FAILURE case but passed validation"


@pytest.fixture
def valid_changeset() -> dict:
    with open(GOLDEN / "changeset" / "valid" / "cs-context-pnpm.json", encoding="utf-8") as f:
        return json.load(f)


def test_changeset_rejects_loop_target(valid_changeset):
    cs = copy.deepcopy(valid_changeset)
    cs["targets"] = [".monumentum/journal/2026-08.ndjson"]
    assert validate_object("changeset", cs)


def test_changeset_rejects_loop_dir_itself(valid_changeset):
    cs = copy.deepcopy(valid_changeset)
    cs["targets"] = [".monumentum"]
    assert validate_object("changeset", cs)


def test_changeset_allows_loop_prefix_name(valid_changeset):
    # ".loopy/x" is NOT inside .monumentum/ and must stay legal.
    cs = copy.deepcopy(valid_changeset)
    cs["targets"] = [".loopy/notes.md"]
    assert validate_object("changeset", cs) == []


def test_changeset_rejects_absolute_and_backslash_targets(valid_changeset):
    for bad in ["/etc/passwd", "C:/x.md", "a\\b.md", "a/../b.md"]:
        cs = copy.deepcopy(valid_changeset)
        cs["targets"] = [bad]
        assert validate_object("changeset", cs), f"target {bad!r} must be rejected"


def test_changeset_ext_is_open_but_root_is_closed(valid_changeset):
    cs = copy.deepcopy(valid_changeset)
    cs["ext"] = {"anything": {"nested": True}}
    assert validate_object("changeset", cs) == []
    cs["custom_field"] = 1
    assert validate_object("changeset", cs)


def test_changeset_bad_timestamp_rejected(valid_changeset):
    cs = copy.deepcopy(valid_changeset)
    cs["created"] = "yesterday"
    assert validate_object("changeset", cs)


def test_evidence_human_feedback_needs_no_artifact():
    ev = {
        "id": "ev-x1",
        "kind": "human",
        "grader": "independent",
        "format": "human-feedback",
        "summary": {"metric": "approval"},
    }
    assert validate_object("evidence", ev) == []


def test_evidence_machine_formats_need_artifact():
    for fmt in ["inspect-log", "lm-eval", "otel-genai", "command-transcript"]:
        ev = {
            "id": "ev-x2",
            "kind": "eval",
            "grader": "independent",
            "format": fmt,
            "summary": {"metric": "m"},
        }
        assert validate_object("evidence", ev), f"format {fmt} must require artifact"


def test_journal_genesis_rules():
    genesis = {
        "seq": 0,
        "prev": None,
        "ts": "2026-08-30T09:00:00Z",
        "event": "genesis",
        "actor": "executor/monumentum@0.1.0",
    }
    assert validate_object("journal-entry", genesis) == []
    non_genesis_at_zero = dict(genesis, event="applied")
    assert validate_object("journal-entry", non_genesis_at_zero)


def test_policy_requires_loop_protection():
    policy = load_instance(GOLDEN / "policy" / "valid" / "default-policy.yaml")
    policy["protected"] = ["something/**"]
    assert validate_object("policy", policy)
