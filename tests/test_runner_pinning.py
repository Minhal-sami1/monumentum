"""Regression guard for DEC-041: the conformance runner must pin a relative
interpreter LEXICALLY, never through Path.resolve().

On Linux a venv's bin/python is a symlink to the system interpreter, so
resolving it drops the virtualenv and every conformance case fails with
`No module named 'agentloop'`. Windows venvs copy the binary, which is why
the defect was invisible there and shipped.

These tests always run on every platform. Where the OS permits symlink
creation (Linux, and Windows in developer mode) the strong assertion runs:
the pinned path must still point inside the fake venv. Where it does not,
the lexical assertion still holds the important property.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conformance"))

from runner import pin_executable  # noqa: E402


def _make_fake_venv(tmp_path: Path) -> tuple[Path, Path, bool]:
    """Build a venv-like layout. Returns (venv_python, system_python, is_symlink)."""
    system_bin = tmp_path / "usr" / "bin"
    system_bin.mkdir(parents=True)
    system_python = system_bin / "python3.11"
    system_python.write_text("#!/bin/sh\n", encoding="utf-8")

    venv_bin = tmp_path / "repo" / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    venv_python = venv_bin / "python"
    try:
        os.symlink(system_python, venv_python)
        return venv_python, system_python, True
    except OSError:
        # No symlink privilege (stock Windows): fall back to a copy, which
        # is exactly what a real Windows venv does.
        venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
        return venv_python, system_python, False


def test_relative_interpreter_stays_inside_the_venv(tmp_path, monkeypatch):
    venv_python, system_python, is_symlink = _make_fake_venv(tmp_path)
    repo = tmp_path / "repo"
    monkeypatch.chdir(repo)

    pinned = Path(pin_executable(os.path.join(".venv", "bin", "python")))

    assert pinned.is_absolute()
    # The load-bearing property: the pinned interpreter is still the venv's.
    assert ".venv" in pinned.parts, f"virtualenv dropped from pinned path: {pinned}"
    assert pinned == Path(os.path.normpath(venv_python))
    if is_symlink:
        # The exact regression: resolve() would have produced the system
        # interpreter and silently left the virtualenv.
        assert pinned != Path(os.path.normpath(venv_python.resolve()))
        assert pinned.resolve() == system_python.resolve()


def test_absolute_interpreter_is_left_alone(tmp_path):
    assert pin_executable(sys.executable) == sys.executable


def test_unknown_relative_path_is_returned_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert pin_executable("python3") == "python3"


def test_windows_exe_suffix_is_found(tmp_path, monkeypatch):
    scripts = tmp_path / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    pinned = Path(pin_executable(os.path.join(".venv", "Scripts", "python")))
    assert pinned.name == "python.exe"
    assert ".venv" in pinned.parts
