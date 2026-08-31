#!/usr/bin/env python
"""Prove no metric value is hard-coded in the paper prose (forbidden move 4).

Scans the paper .tex for decimal/percentage numbers that look like results.
Allowed numbers: section/figure/citation years (4-digit 19xx/20xx), RFC
numbers, article numbers written as \\S or 'Article N', ISO/standard numbers,
and anything inside \\input-ed generated files (which this check skips).
Any other numeric literal must come through a \\<macro>, not the prose.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# metric-shaped literals: decimals, percentages, or "N s"/"N tokens"
SUSPECT = re.compile(r"(?<![\\A-Za-z0-9])\d+\.\d+|\d+\s*\\%|\d+\s*(seconds|tokens|ms)\b")

# lines that legitimately contain numbers (allow-list of contexts)
ALLOWED_LINE = re.compile(
    r"RFC\s*\d+|Article\s*\d+|ISO/IEC\s*\d+|AI Act|2119|6962|42001|1689|"
    r"loop/v0\.1|Python~?\s*3\.\d+|ed25519|SHA-?256|draft 2020-12|Apache-2\.0|"
    r"\\newcommand|\\input|\\cite|\\ref|\\label|\\section|\\subsection|"
    r"v0\.1|20\d\d|19\d\d"
)

# LaTeX layout numbers are typography, not results: package options and any
# number carrying a TeX length unit.
LAYOUT = re.compile(
    r"\\usepackage|\\documentclass|\\includegraphics|"
    r"\d+(\.\d+)?\s*(in|em|ex|pt|cm|mm|\\textwidth|\\columnwidth|\\linewidth)"
)


def main() -> int:
    path = Path(sys.argv[1])
    problems = []
    in_verbatim = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("%"):
            continue
        if re.search(r"\\begin\{(verbatim|lstlisting)\}", line):
            in_verbatim = True
            continue
        if re.search(r"\\end\{(verbatim|lstlisting)\}", line):
            in_verbatim = False
            continue
        if in_verbatim:
            continue
        if ALLOWED_LINE.search(line) or LAYOUT.search(line):
            continue
        for match in SUSPECT.finditer(line):
            problems.append(
                f"{path.name}:{i}: possible hard-coded metric "
                f"{match.group()!r}: {stripped}")

    if problems:
        print("HARD-CODED METRIC CHECK FAILED — route these through metrics.tex macros:")
        for p in problems:
            print(f"  {p}")
        return 1
    print("no hard-coded metrics in the paper prose: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
