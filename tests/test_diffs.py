"""Unified diff parser/applier tests."""

import pytest

from agentloop.diffs import DiffError, apply_patch_set, parse_unified_diff

MODIFY = """\
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up.
"""

CREATE = """\
--- /dev/null
+++ b/notes/new.md
@@ -0,0 +1,2 @@
+line one
+line two
"""

DELETE = """\
--- a/old.md
+++ /dev/null
@@ -1,2 +0,0 @@
-stale line
-another stale line
"""


def test_modify():
    patches = parse_unified_diff(MODIFY)
    out = apply_patch_set(patches, {"AGENTS.md": "# Agent notes\n\nUse npm install to set up.\n"})
    assert out["AGENTS.md"] == "# Agent notes\n\nUse pnpm install to set up.\n"


def test_create():
    patches = parse_unified_diff(CREATE)
    out = apply_patch_set(patches, {"notes/new.md": None})
    assert out["notes/new.md"] == "line one\nline two\n"


def test_delete():
    patches = parse_unified_diff(DELETE)
    out = apply_patch_set(patches, {"old.md": "stale line\nanother stale line\n"})
    assert out["old.md"] is None


def test_context_mismatch_rejected():
    patches = parse_unified_diff(MODIFY)
    with pytest.raises(DiffError, match="mismatch"):
        apply_patch_set(patches, {"AGENTS.md": "# Different file\n\nUse npm install to set up.\n"})


def test_missing_file_rejected():
    patches = parse_unified_diff(MODIFY)
    with pytest.raises(DiffError, match="missing"):
        apply_patch_set(patches, {"AGENTS.md": None})


def test_create_over_existing_rejected():
    patches = parse_unified_diff(CREATE)
    with pytest.raises(DiffError, match="already has content"):
        apply_patch_set(patches, {"notes/new.md": "occupied\n"})


def test_multi_hunk():
    text = "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"
    diff = """\
--- a/f.txt
+++ b/f.txt
@@ -1,2 +1,2 @@
-a
+A
 b
@@ -9,2 +9,2 @@
 i
-j
+J
"""
    out = apply_patch_set(parse_unified_diff(diff), {"f.txt": text})
    assert out["f.txt"] == "A\nb\nc\nd\ne\nf\ng\nh\ni\nJ\n"


def test_bad_counts_rejected():
    bad = """\
--- a/f.txt
+++ b/f.txt
@@ -1,3 +1,1 @@
-a
+A
"""
    with pytest.raises(DiffError, match="counts"):
        parse_unified_diff(bad)


def test_empty_diff_rejected():
    with pytest.raises(DiffError, match="no file patches"):
        parse_unified_diff("just some text\n")
