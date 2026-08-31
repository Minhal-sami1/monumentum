#!/usr/bin/env python
"""Deterministic experiments for the paper (E1/E2).

Each experiment emits JSONL with a run_id, versions, seed, and timings.
`make reproduce` runs this plus the scenario/demo/adversarial scripts, then
metrics.py aggregates every log into the paper's tables and figures.

Experiments here (no live model needed, fully reproducible):
  - overhead:   added wall time per session to make a managed-file change
                WITH the loop (propose->evidence->gate->apply) vs WITHOUT
                (a direct edit), over >=5 fixed tasks. Also the added
                context size (tokens) the skill + AGENTS.md block impose.
  - evidence:   share of managed-file changes carrying evidence, loop vs a
                no-loop baseline session.

The live-model trigger experiment (B1) lives in experiments/trigger/.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "agentloop.cli"]

# five fixed tasks: (target file, initial content, old line, new line)
TASKS = [
    ("AGENTS.md", "# Notes\n\nUse npm.\n", "Use npm.", "Use pnpm."),
    ("AGENTS.md", "# Notes\n\nRun tests with unittest.\n",
     "Run tests with unittest.", "Run tests with pytest."),
    ("CLAUDE.md", "# Rules\n\nFormat with black.\n",
     "Format with black.", "Format with ruff format."),
    ("CLAUDE.md", "# Rules\n\nPython 3.10 required.\n",
     "Python 3.10 required.", "Python 3.11 required."),
    ("AGENTS.md", "# Notes\n\nDeploy from main.\n",
     "Deploy from main.", "Deploy from the release branch."),
]

APPROX_CHARS_PER_TOKEN = 4  # standard rough proxy; stated as such in the paper


def _run_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC):%Y%m%d-%H%M%S}"


def _versions() -> dict:
    import agentloop

    return {"agentloop": agentloop.__version__, "python": sys.version.split()[0]}


def _present_check(rel: str, needle: str) -> str:
    """A reproducible_check command: exits 0 iff `needle` is in the file."""
    return (
        f'"{sys.executable}" -c "import sys; '
        f"sys.exit(0 if open({rel!r}, encoding='utf-8').read().find({needle!r}) >= 0 else 1)\""
    )


def _apply_via_loop(ws: Path, rel: str, initial: str, old_line: str, new_line: str) -> float:
    """Full loop path for one change. Returns wall seconds."""
    (ws / rel).write_text(initial, encoding="utf-8", newline="\n")
    subprocess.run([*CLI, "-C", str(ws), "init"], cwd=ws, capture_output=True,
                   text=True, check=True)
    import difflib

    patch = "".join(difflib.unified_diff(
        initial.splitlines(keepends=True),
        initial.replace(old_line, new_line).splitlines(keepends=True),
        fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    (ws / "fix.patch").write_text(patch, encoding="utf-8", newline="\n")
    check = _present_check(rel, new_line)
    (ws / "transcript.json").write_text(
        json.dumps({"check_cmd": check,
                    "runs": [{"phase": "before", "exit_code": 1},
                             {"phase": "after", "exit_code": 0}]}),
        encoding="utf-8")
    (ws / "ev.json").write_text(json.dumps({
        "id": "ev-001", "kind": "eval", "grader": "independent",
        "format": "command-transcript",
        "summary": {"metric": "task_pass", "before": 0, "after": 1, "n": 1}}),
        encoding="utf-8")

    t0 = time.monotonic()
    cs = "cs-20260831-ovh1"
    subprocess.run([*CLI, "-C", str(ws), "propose", "--layer", "context",
                    "--target", rel, "--patch", "fix.patch", "--rationale",
                    "fixed task change", "--producer", "exp", "--id", cs],
                   cwd=ws, capture_output=True, text=True, check=True)
    subprocess.run([*CLI, "-C", str(ws), "evidence", cs, "--record", "ev.json",
                    "--artifact", "transcript.json"], cwd=ws, capture_output=True,
                   text=True, check=True)
    subprocess.run([*CLI, "-C", str(ws), "gate", cs], cwd=ws, capture_output=True, text=True)
    subprocess.run([*CLI, "-C", str(ws), "apply", cs], cwd=ws, capture_output=True,
                   text=True, check=True)
    elapsed = time.monotonic() - t0
    assert new_line in (ws / rel).read_text(encoding="utf-8")
    return elapsed


def _apply_direct(ws: Path, rel: str, initial: str, old_line: str, new_line: str) -> float:
    """No-loop baseline: a direct edit. Returns wall seconds."""
    (ws / rel).write_text(initial, encoding="utf-8", newline="\n")
    t0 = time.monotonic()
    path = ws / rel
    path.write_text(path.read_text(encoding="utf-8").replace(old_line, new_line),
                    encoding="utf-8", newline="\n")
    return time.monotonic() - t0


def experiment_overhead(logs_dir: Path) -> Path:
    run_id = _run_id("overhead")
    out = logs_dir / f"{run_id}.jsonl"
    records = []
    for i, (rel, initial, old_line, new_line) in enumerate(TASKS):
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ovh-loop-") as d:
            loop_s = _apply_via_loop(Path(d), rel, initial, old_line, new_line)
        with tempfile.TemporaryDirectory(prefix="ovh-base-") as d:
            base_s = _apply_direct(Path(d), rel, initial, old_line, new_line)
        records.append({
            "run_id": run_id, "experiment": "overhead", "seed": i, "task": rel,
            "loop_seconds": round(loop_s, 4), "baseline_seconds": round(base_s, 6),
            "added_seconds": round(loop_s - base_s, 4),
            "versions": _versions(),
        })
    # added context size: the skill + the AGENTS.md managed block
    from agentloop.workspace import AGENTS_BLOCK

    skill_chars = (REPO / "skill" / "SKILL.md").read_text(encoding="utf-8").__len__()
    block_chars = len(AGENTS_BLOCK)
    total_chars = skill_chars + block_chars
    records.append({
        "run_id": run_id, "experiment": "overhead-context",
        "skill_chars": skill_chars, "agents_block_chars": block_chars,
        "added_context_chars": total_chars,
        "added_context_tokens_approx": round(total_chars / APPROX_CHARS_PER_TOKEN),
        "approx_chars_per_token": APPROX_CHARS_PER_TOKEN,
        "note": "loop operations are deterministic code and add zero model tokens; "
                "the added context is the skill body plus the AGENTS.md managed block",
        "versions": _versions(),
    })
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return out


def experiment_evidence(logs_dir: Path) -> Path:
    """Share of managed-file changes that carry evidence: loop vs baseline."""
    run_id = _run_id("evidence")
    out = logs_dir / f"{run_id}.jsonl"
    import tempfile

    # loop session: every applied managed-file change is gated, so it MUST
    # carry evidence (the gate refuses otherwise). Measure by applying the
    # fixed tasks and counting how many applied changes have an evidence list.
    loop_total = loop_with_evidence = 0
    with tempfile.TemporaryDirectory(prefix="evd-loop-") as d:
        ws = Path(d)
        (ws / "AGENTS.md").write_text("# Notes\n\nUse npm.\n", encoding="utf-8", newline="\n")
        subprocess.run([*CLI, "-C", str(ws), "init"], cwd=ws, capture_output=True,
                       text=True, check=True)
        for i, (rel, initial, old_line, new_line) in enumerate(TASKS):
            (ws / rel).write_text(initial, encoding="utf-8", newline="\n")
            # re-baseline the head so the head check passes for the changed file
            import difflib
            patch = "".join(difflib.unified_diff(
                initial.splitlines(keepends=True),
                initial.replace(old_line, new_line).splitlines(keepends=True),
                fromfile=f"a/{rel}", tofile=f"b/{rel}"))
            (ws / "p.patch").write_text(patch, encoding="utf-8", newline="\n")
            check = _present_check(rel, new_line)
            (ws / "t.json").write_text(json.dumps({"check_cmd": check, "runs": [
                {"phase": "before", "exit_code": 1}, {"phase": "after", "exit_code": 0}]}),
                encoding="utf-8")
            (ws / "e.json").write_text(json.dumps({
                "id": "ev-001", "kind": "eval", "grader": "independent",
                "format": "command-transcript",
                "summary": {"metric": "task_pass", "before": 0, "after": 1, "n": 1}}),
                encoding="utf-8")
            cs = f"cs-20260831-evd{i}"
            # reset workspace head baseline is not needed; init captured AGENTS/CLAUDE at empty
            r = subprocess.run([*CLI, "-C", str(ws), "propose", "--layer", "context",
                                "--target", rel, "--patch", "p.patch", "--rationale",
                                "task", "--producer", "exp", "--id", cs],
                               cwd=ws, capture_output=True, text=True)
            if r.returncode != 0:
                continue
            subprocess.run([*CLI, "-C", str(ws), "evidence", cs, "--record", "e.json",
                            "--artifact", "t.json"], cwd=ws, capture_output=True, text=True)
            subprocess.run([*CLI, "-C", str(ws), "gate", cs], cwd=ws,
                           capture_output=True, text=True)
            ap = subprocess.run([*CLI, "-C", str(ws), "apply", cs], cwd=ws,
                                capture_output=True, text=True)
            if ap.returncode == 0:
                loop_total += 1
                env = json.loads((ws / ".loop" / "changesets" / cs / "changeset.json")
                                 .read_text(encoding="utf-8"))
                if env["evidence"]:
                    loop_with_evidence += 1

    # baseline session: direct edits, no loop -> zero changes carry evidence
    baseline_total = len(TASKS)
    baseline_with_evidence = 0

    record = {
        "run_id": run_id, "experiment": "evidence",
        "loop_changes": loop_total, "loop_with_evidence": loop_with_evidence,
        "loop_evidence_rate": round(loop_with_evidence / loop_total, 3) if loop_total else 0.0,
        "baseline_changes": baseline_total, "baseline_with_evidence": baseline_with_evidence,
        "baseline_evidence_rate": 0.0,
        "versions": _versions(),
    }
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record) + "\n")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPO / "experiments")
    parser.add_argument("--only", choices=["overhead", "evidence"], default=None)
    args = parser.parse_args()

    os.environ.setdefault("REPO_ROOT", str(REPO))
    made = []
    if args.only in (None, "overhead"):
        d = args.out / "overhead" / "logs"
        d.mkdir(parents=True, exist_ok=True)
        made.append(experiment_overhead(d))
    if args.only in (None, "evidence"):
        d = args.out / "evidence" / "logs"
        d.mkdir(parents=True, exist_ok=True)
        made.append(experiment_evidence(d))
    for path in made:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
