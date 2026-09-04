"""Executor-level conformance: reference CLI passes, broken stub fails (D2)."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "conformance" / "runner.py"


def _run(executor: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--executor", executor],
        capture_output=True, text=True, cwd=REPO, timeout=1200,
    )


def test_reference_cli_passes_conformance():
    py = Path(sys.executable).as_posix()
    proc = _run(f'"{py}" -m monumentum.cli')
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_broken_stub_fails_conformance():
    py = Path(sys.executable).as_posix()
    stub = (REPO / "conformance" / "stubs" / "broken_executor.py").as_posix()
    proc = _run(f'"{py}" {stub}')
    assert proc.returncode != 0, "the broken executor stub must fail the suite"
    assert "FAIL" in proc.stdout
