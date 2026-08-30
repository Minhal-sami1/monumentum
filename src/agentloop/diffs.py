"""Strict unified-diff parser and applier.

Deterministic by design: context must match exactly or the apply fails.
Supports multi-file patches, file creation (--- /dev/null), and file
deletion (+++ /dev/null). Lines are joined with \\n; the
"\\ No newline at end of file" marker is honored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class DiffError(Exception):
    pass


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)  # each starts with ' ', '-', '+', or '\\'


@dataclass
class FilePatch:
    old_path: str | None  # None = file creation
    new_path: str | None  # None = file deletion
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def target(self) -> str:
        path = self.new_path if self.new_path is not None else self.old_path
        assert path is not None
        return path


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _clean_path(raw: str) -> str | None:
    path = raw.split("\t")[0].strip()
    if path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path


def parse_unified_diff(text: str) -> list[FilePatch]:
    patches: list[FilePatch] = []
    lines = text.split("\n")
    i = 0
    current: FilePatch | None = None
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- "):
            if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
                raise DiffError(f"'---' header without '+++' at line {i + 1}")
            old_path = _clean_path(line[4:])
            new_path = _clean_path(lines[i + 1][4:])
            if old_path is None and new_path is None:
                raise DiffError("both sides /dev/null")
            current = FilePatch(old_path=old_path, new_path=new_path)
            patches.append(current)
            i += 2
            continue
        match = _HUNK_RE.match(line)
        if match:
            if current is None:
                raise DiffError(f"hunk before file header at line {i + 1}")
            hunk = Hunk(
                old_start=int(match.group(1)),
                old_count=int(match.group(2) or "1"),
                new_start=int(match.group(3)),
                new_count=int(match.group(4) or "1"),
            )
            current.hunks.append(hunk)
            i += 1
            old_seen = new_seen = 0
            while i < len(lines) and (old_seen < hunk.old_count or new_seen < hunk.new_count):
                body = lines[i]
                if body.startswith("\\"):
                    hunk.lines.append(body)
                    i += 1
                    continue
                if not body:
                    body = " "  # empty context line
                tag = body[0]
                if tag == " ":
                    old_seen += 1
                    new_seen += 1
                elif tag == "-":
                    old_seen += 1
                elif tag == "+":
                    new_seen += 1
                else:
                    raise DiffError(f"unexpected line inside hunk at line {i + 1}: {body!r}")
                hunk.lines.append(body)
                i += 1
            # trailing "no newline" marker
            if i < len(lines) and lines[i].startswith("\\"):
                hunk.lines.append(lines[i])
                i += 1
            if old_seen != hunk.old_count or new_seen != hunk.new_count:
                raise DiffError(
                    f"hunk line counts do not match header (@@ -{hunk.old_start},{hunk.old_count} "
                    f"+{hunk.new_start},{hunk.new_count} @@)"
                )
            continue
        i += 1
    if not patches:
        raise DiffError("no file patches found in diff")
    return patches


def _apply_hunks(content: str | None, patch: FilePatch) -> str | None:
    if patch.old_path is None:
        old_lines: list[str] = []
        old_ends_nl = True
        if content is not None:
            raise DiffError(f"creation patch but target already has content: {patch.target}")
    else:
        if content is None:
            raise DiffError(f"patch expects existing file, target missing: {patch.old_path}")
        old_lines = content.split("\n")
        old_ends_nl = old_lines[-1] == ""
        if old_ends_nl:
            old_lines.pop()

    if patch.new_path is None:
        # deletion: verify hunks consume the whole file, then delete
        expected = [ln[1:] for h in patch.hunks for ln in h.lines if ln.startswith("-")]
        if expected != old_lines:
            raise DiffError(f"deletion patch does not match current content of {patch.old_path}")
        return None

    new_lines: list[str] = []
    cursor = 0  # index into old_lines
    new_ends_nl = old_ends_nl
    for hunk in patch.hunks:
        start = hunk.old_start - 1 if hunk.old_count > 0 else hunk.old_start
        if start < cursor:
            raise DiffError("overlapping hunks")
        new_lines.extend(old_lines[cursor:start])
        cursor = start
        pending_nl_marker_applies_to_new = False
        for raw in hunk.lines:
            if raw.startswith("\\"):
                # "no newline at end of file" applies to whichever side the
                # previous line belonged to; only the new side matters here.
                if pending_nl_marker_applies_to_new:
                    new_ends_nl = False
                continue
            tag, text = raw[0], raw[1:]
            if tag == " ":
                if cursor >= len(old_lines) or old_lines[cursor] != text:
                    found = old_lines[cursor] if cursor < len(old_lines) else "<EOF>"
                    raise DiffError(
                        f"context mismatch in {patch.target} at line {cursor + 1}: "
                        f"expected {text!r}, found {found!r}"
                    )
                new_lines.append(text)
                cursor += 1
                pending_nl_marker_applies_to_new = True
            elif tag == "-":
                if cursor >= len(old_lines) or old_lines[cursor] != text:
                    found = old_lines[cursor] if cursor < len(old_lines) else "<EOF>"
                    raise DiffError(
                        f"removal mismatch in {patch.target} at line {cursor + 1}: "
                        f"expected {text!r}, found {found!r}"
                    )
                cursor += 1
                pending_nl_marker_applies_to_new = False
            else:  # '+'
                new_lines.append(text)
                pending_nl_marker_applies_to_new = True
    new_lines.extend(old_lines[cursor:])
    out = "\n".join(new_lines)
    if new_ends_nl:
        out += "\n"
    return out


def apply_patch_set(
    patches: list[FilePatch], read: dict[str, str | None]
) -> dict[str, str | None]:
    """Apply parsed patches. `read` maps target path -> current content
    (None = file absent). Returns target path -> new content (None = delete).
    """
    out: dict[str, str | None] = {}
    for patch in patches:
        key = patch.target
        current = read.get(patch.old_path if patch.old_path is not None else key)
        out[key] = _apply_hunks(current, patch)
    return out
