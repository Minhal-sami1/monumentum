"""Load and apply the five normative JSON Schemas.

The schema files in spec/schemas/ are the normative artifacts. This module
only loads them and runs a Draft 2020-12 validator with format checking.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

# Object type -> schema file stem. These five names are the five objects.
OBJECT_TYPES = {
    "changeset": "changeset.schema.json",
    "evidence": "evidence.schema.json",
    "policy": "policy.schema.json",
    "journal-entry": "journal-entry.schema.json",
    "registry": "registry.schema.json",
}

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_DIR = _REPO_ROOT / "spec" / "schemas"


def schema_dir() -> Path:
    """Directory holding the normative schema files."""
    return DEFAULT_SCHEMA_DIR


@cache
def load_schema(object_type: str) -> dict:
    """Load one schema by object type name. Raises KeyError for unknown types."""
    filename = OBJECT_TYPES[object_type]
    path = schema_dir() / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@cache
def get_validator(object_type: str) -> Draft202012Validator:
    """Compiled validator for one object type. check_schema runs once here."""
    schema = load_schema(object_type)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_object(object_type: str, obj: object) -> list[str]:
    """Validate a parsed object. Returns a list of error strings; empty means valid."""
    validator = get_validator(object_type)
    errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
    out = []
    for err in errors:
        where = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{where}: {err.message}")
    return out


def load_instance(path: Path) -> object:
    """Parse a golden/instance file: .json via json, .yaml/.yml via safe_load."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    raise ValueError(f"unsupported instance file type: {path}")
