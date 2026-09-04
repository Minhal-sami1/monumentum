"""check-schemas: validate the golden corpus against the normative schemas.

Contract (milestone m1 gate):
- every file under golden/<type>/valid/  MUST validate
- every file under golden/<type>/invalid/ MUST fail validation
- any deviation, unknown type directory, or unreadable file exits non-zero
"""

from __future__ import annotations

import sys
from pathlib import Path

from monumentum.schemas import OBJECT_TYPES, get_validator, load_instance, validate_object

GOLDEN_SUBDIRS = ("valid", "invalid")


def check_schemas(golden_dir: Path, out=sys.stdout) -> int:
    """Run the full golden-corpus check. Returns process exit code."""
    failures: list[str] = []
    counts = {"valid": 0, "invalid": 0}

    # 1. All five schemas must compile.
    for object_type in OBJECT_TYPES:
        try:
            get_validator(object_type)
        except Exception as exc:  # noqa: BLE001 - report any compile failure
            failures.append(f"schema compile failed for {object_type}: {exc}")
    if failures:
        _report(failures, counts, out)
        return 1

    if not golden_dir.is_dir():
        print(f"golden directory not found: {golden_dir}", file=out)
        return 1

    # 2. Only known object-type directories are allowed.
    for entry in sorted(golden_dir.iterdir()):
        if entry.is_dir() and entry.name not in OBJECT_TYPES:
            failures.append(f"unknown object-type directory: {entry.name}")

    # 3. valid/ must pass, invalid/ must fail.
    for object_type in sorted(OBJECT_TYPES):
        type_dir = golden_dir / object_type
        if not type_dir.is_dir():
            failures.append(f"missing golden directory: {object_type}/")
            continue
        for expectation in GOLDEN_SUBDIRS:
            sub = type_dir / expectation
            if not sub.is_dir():
                failures.append(f"missing golden directory: {object_type}/{expectation}/")
                continue
            files = sorted(p for p in sub.rglob("*") if p.is_file())
            if not files:
                failures.append(f"empty golden directory: {object_type}/{expectation}/")
            for path in files:
                rel = path.relative_to(golden_dir)
                try:
                    instance = load_instance(path)
                except Exception as exc:  # noqa: BLE001 - malformed file is a failure
                    failures.append(f"{rel}: cannot parse: {exc}")
                    continue
                errors = validate_object(object_type, instance)
                if expectation == "valid" and errors:
                    failures.append(f"{rel}: MUST validate but failed: {errors[0]}")
                elif expectation == "invalid" and not errors:
                    failures.append(f"{rel}: REQUIRED-FAILURE case passed validation")
                else:
                    counts[expectation] += 1

    _report(failures, counts, out)
    return 1 if failures else 0


def _report(failures: list[str], counts: dict[str, int], out) -> None:
    for line in failures:
        print(f"FAIL {line}", file=out)
    print(
        f"check-schemas: {counts['valid']} valid passed, "
        f"{counts['invalid']} required-failure failed correctly, "
        f"{len(failures)} problems",
        file=out,
    )
