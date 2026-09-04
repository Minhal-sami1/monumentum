"""CLI surface tests for m1."""

from pathlib import Path

import pytest

from monumentum.cli import main

REPO = Path(__file__).resolve().parents[1]


def test_check_schemas_exit_zero():
    assert main(["check-schemas", "--golden", str(REPO / "conformance" / "golden")]) == 0


def test_check_schemas_missing_dir_exit_one(tmp_path):
    assert main(["check-schemas", "--golden", str(tmp_path / "absent")]) == 1


def test_version_flag():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_no_command_is_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
