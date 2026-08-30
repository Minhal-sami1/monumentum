#!/usr/bin/env python
"""Executor-level conformance runner (spec §14).

Drives ANY executor through the subprocess contract and checks the file
plane afterwards. The runner deliberately does not import the agentloop
package: it sees an executor exactly the way a stranger's implementation
would be seen.

Subprocess contract (normative for conformance):

    <executor-cmd> -C <workspace> <verb> [args...]

Verbs and exit codes:
    init                                       0 on success
    propose (--from-dir D | --layer L --target T... --patch F
             --rationale R --producer P --id ID)   0 valid, 1 rejected
    evidence <id> --record F [--artifact F]    0 on success
    gate <id>                                  0 approved, 1 rejected, 2 queued
    apply <id>                                 0 applied, 1 rejected/failed
    approve <id> --actor A                     0 applied, 1 refused
    reject <id> --actor A [--reason R]         0 rejected
    rollback <id> [--actor A]                  0 rolled back
    verify [path]                              0 intact, 1 problems
    log --json                                 0; one JSON entry per line

Case format: conformance/cases/<id>/case.yaml plus a files/ dir copied
into a fresh workspace. Steps run in order; the journal event sequence
and file expectations are checked at the end. See conformance/README.md.
"""

from __future__ import annotations

import argparse
import glob as globmod
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


class CaseFailure(Exception):
    pass


def run_step_cmd(
    executor: list[str], workspace: Path, args: list[str]
) -> subprocess.CompletedProcess:
    cmd = [*executor, "-C", str(workspace), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=workspace)


def substitute(value: str, case_dir: Path, workspace: Path) -> str:
    return value.replace("{case}", str(case_dir)).replace("{ws}", str(workspace))


def check_expect_file(spec: dict, workspace: Path) -> None:
    path = workspace / spec["path"]
    if spec.get("absent"):
        if path.exists():
            raise CaseFailure(f"expected {spec['path']} to be absent, it exists")
        return
    if not path.is_file():
        raise CaseFailure(f"expected file missing: {spec['path']}")
    content = path.read_text(encoding="utf-8")
    if "equals" in spec and content != spec["equals"]:
        raise CaseFailure(
            f"{spec['path']} content mismatch:\n--- expected ---\n{spec['equals']}"
            f"\n--- actual ---\n{content}"
        )
    if "contains" in spec and spec["contains"] not in content:
        raise CaseFailure(f"{spec['path']} does not contain {spec['contains']!r}")
    if "not_contains" in spec and spec["not_contains"] in content:
        raise CaseFailure(f"{spec['path']} must not contain {spec['not_contains']!r}")


def do_edit_file(spec: dict, workspace: Path) -> None:
    matches = sorted(globmod.glob(str(workspace / spec["path"])))
    if not matches:
        raise CaseFailure(f"edit_file: no file matches {spec['path']}")
    path = Path(matches[0])
    data = path.read_text(encoding="utf-8")
    if spec["find"] not in data:
        raise CaseFailure(f"edit_file: {spec['find']!r} not found in {spec['path']}")
    path.write_text(data.replace(spec["find"], spec["replace"], 1), encoding="utf-8")


def journal_events(workspace: Path) -> list[str]:
    events = []
    journal_dir = workspace / ".loop" / "journal"
    if not journal_dir.is_dir():
        return events
    for file in sorted(journal_dir.glob("*.ndjson")):
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line)["event"])
    return events


def run_case(case_dir: Path, executor: list[str], keep: bool = False) -> None:
    case = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    workspace = Path(tempfile.mkdtemp(prefix=f"loopconf-{case_dir.name}-"))
    try:
        files_dir = case_dir / "files"
        if files_dir.is_dir():
            shutil.copytree(files_dir, workspace, dirs_exist_ok=True)

        for i, step in enumerate(case.get("steps", [])):
            if "run" in step:
                args = [substitute(str(a), case_dir, workspace) for a in step["run"]]
                proc = run_step_cmd(executor, workspace, args)
                expected = step.get("expect_exit", 0)
                if proc.returncode != expected:
                    raise CaseFailure(
                        f"step {i + 1} {' '.join(args)}: exit {proc.returncode}, "
                        f"expected {expected}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
                    )
            elif "expect_file" in step:
                check_expect_file(step["expect_file"], workspace)
            elif "edit_file" in step:
                do_edit_file(step["edit_file"], workspace)
            else:
                raise CaseFailure(f"step {i + 1}: unknown step type {sorted(step)}")

        expected_events = case.get("expected_events")
        if expected_events is not None:
            actual = journal_events(workspace)
            if actual != expected_events:
                raise CaseFailure(
                    f"journal event sequence mismatch:\nexpected: {expected_events}\n"
                    f"actual:   {actual}"
                )

        if case.get("final_verify", True):
            proc = run_step_cmd(executor, workspace, ["verify"])
            if proc.returncode != 0:
                raise CaseFailure(
                    f"final verify failed (exit {proc.returncode})\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
    finally:
        if keep:
            print(f"  workspace kept: {workspace}")
        else:
            shutil.rmtree(workspace, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Loop conformance runner")
    parser.add_argument(
        "--executor", required=True,
        help="executor command, e.g. 'python -m agentloop.cli'",
    )
    parser.add_argument("--cases", type=Path, default=HERE / "cases")
    parser.add_argument("--only", help="run a single case id")
    parser.add_argument("--keep", action="store_true", help="keep temp workspaces")
    args = parser.parse_args()

    executor = shlex.split(args.executor)
    # A relative interpreter path (e.g. .venv/Scripts/python) breaks once the
    # subprocess runs from a temp workspace; pin it to an absolute path.
    exe = Path(executor[0])
    if not exe.is_absolute():
        for candidate in (Path.cwd() / exe, Path.cwd() / (str(exe) + ".exe")):
            if candidate.exists():
                executor[0] = str(candidate.resolve())
                break
    case_dirs = sorted(d for d in args.cases.iterdir() if (d / "case.yaml").is_file())
    if args.only:
        case_dirs = [d for d in case_dirs if d.name == args.only]
    if not case_dirs:
        print("no conformance cases found", file=sys.stderr)
        return 1

    failures = 0
    for case_dir in case_dirs:
        try:
            run_case(case_dir, executor, keep=args.keep)
            print(f"PASS {case_dir.name}")
        except CaseFailure as exc:
            failures += 1
            print(f"FAIL {case_dir.name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - infrastructure failure
            failures += 1
            print(f"ERROR {case_dir.name}: {exc}")
    print(f"conformance: {len(case_dirs) - failures}/{len(case_dirs)} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
