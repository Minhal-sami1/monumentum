"""Tests for the check-schemas golden-corpus checker."""

import io
import json
import shutil
from pathlib import Path

from agentloop.check import check_schemas

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "conformance" / "golden"


def run(golden: Path) -> tuple[int, str]:
    buf = io.StringIO()
    code = check_schemas(golden, out=buf)
    return code, buf.getvalue()


def test_real_corpus_passes():
    code, output = run(GOLDEN)
    assert code == 0, output


def test_missing_golden_dir_fails(tmp_path):
    code, _ = run(tmp_path / "nope")
    assert code == 1


def _copy_corpus(tmp_path: Path) -> Path:
    dst = tmp_path / "golden"
    shutil.copytree(GOLDEN, dst)
    return dst


def test_broken_valid_file_fails(tmp_path):
    corpus = _copy_corpus(tmp_path)
    target = corpus / "changeset" / "valid" / "cs-minimal.json"
    cs = json.loads(target.read_text(encoding="utf-8"))
    del cs["rationale"]
    target.write_text(json.dumps(cs), encoding="utf-8")
    code, output = run(corpus)
    assert code == 1
    assert "MUST validate but failed" in output


def test_passing_invalid_file_fails(tmp_path):
    corpus = _copy_corpus(tmp_path)
    good = (corpus / "changeset" / "valid" / "cs-minimal.json").read_text(encoding="utf-8")
    (corpus / "changeset" / "invalid" / "sneaky-valid.json").write_text(good, encoding="utf-8")
    code, output = run(corpus)
    assert code == 1
    assert "REQUIRED-FAILURE case passed validation" in output


def test_unknown_type_dir_fails(tmp_path):
    corpus = _copy_corpus(tmp_path)
    (corpus / "mystery").mkdir()
    code, output = run(corpus)
    assert code == 1
    assert "unknown object-type directory" in output


def test_empty_expectation_dir_fails(tmp_path):
    corpus = _copy_corpus(tmp_path)
    sub = corpus / "registry" / "invalid"
    for f in sub.iterdir():
        f.unlink()
    code, output = run(corpus)
    assert code == 1
    assert "empty golden directory" in output


def test_unparseable_file_fails(tmp_path):
    corpus = _copy_corpus(tmp_path)
    (corpus / "evidence" / "valid" / "broken.json").write_text("{not json", encoding="utf-8")
    code, output = run(corpus)
    assert code == 1
    assert "cannot parse" in output
