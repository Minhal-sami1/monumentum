"""Policy loading, allowlist matching (I4), and level arithmetic (spec §7)."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

import yaml

from agentloop.hashing import sha256_file
from agentloop.schemas import validate_object

LEVELS = ["L0", "L1", "L2", "L3"]


class PolicyError(Exception):
    pass


@dataclass
class LoadedPolicy:
    data: dict
    sha256: str

    def class_policy(self, layer: str) -> dict:
        return self.data["envelope"][layer]

    def declared_level(self, layer: str) -> str:
        return self.class_policy(layer)["level"]

    def gates(self, layer: str) -> list[str]:
        return self.class_policy(layer)["gates"]

    def targets_allow(self, layer: str) -> list[str]:
        return self.class_policy(layer)["targets_allow"]

    def protected(self) -> list[str]:
        return self.data["protected"]

    def de_escalation(self) -> dict | None:
        return self.data.get("de_escalation")


def load_policy(path: Path) -> LoadedPolicy:
    if not path.is_file():
        raise PolicyError(f"policy file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = validate_object("policy", data)
    if errors:
        raise PolicyError(f"policy invalid: {errors[0]}")
    return LoadedPolicy(data=data, sha256=sha256_file(path))


def glob_match(target: str, pattern: str) -> bool:
    """Glob match with `**` crossing directory separators.

    fnmatch treats `*` as crossing `/` already, which makes `**` behave the
    same; that is acceptable for v0.1 allowlists (documented in the spec).
    A pattern like `dir/**` must also match nested files.
    """
    if fnmatch.fnmatch(target, pattern):
        return True
    return bool(pattern.endswith("/**") and fnmatch.fnmatch(target, pattern[:-3] + "/*"))


def target_allowed(target: str, allow: list[str], protected: list[str]) -> tuple[bool, str]:
    """Invariants I1 and I4. Returns (allowed, reason-if-not)."""
    for pattern in protected:
        if glob_match(target, pattern):
            return False, f"target {target} matches protected pattern {pattern} (I1)"
    for pattern in allow:
        if glob_match(target, pattern):
            return True, ""
    return False, f"target {target} matches no targets_allow pattern (I4)"


def level_index(level: str) -> int:
    return LEVELS.index(level)


def drop_level(level: str, drop: int) -> str:
    return LEVELS[max(0, level_index(level) - drop)]
