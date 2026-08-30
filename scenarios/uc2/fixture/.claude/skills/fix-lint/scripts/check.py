#!/usr/bin/env python
"""Lint checker bundled with the fix-lint skill.

BROKEN: it calls a helper that was renamed in the last refactor.
Running it crashes with AttributeError - the failure UC2 repairs.
"""
import sys


def count_todos(text):
    return text.count("TODO")


def main():
    # the helper was renamed to count_todos, this call is stale
    total = sys.modules[__name__].count_todo_items("TODO: one\nTODO: two\n")
    print(f"todos: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
