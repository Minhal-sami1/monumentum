"""The fixture project's real test suite (the observation window runs it)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tools.textutil import slugify  # noqa: E402


def test_basic():
    assert slugify("Hello World") == "hello-world"


def test_punctuation_stripped():
    assert slugify("What's New? (2026)") == "whats-new-2026"


def test_collapse_separators():
    assert slugify("a  -  b") == "a-b"


def test_unicode_kept():
    assert slugify("Café Menu") == "café-menu"
