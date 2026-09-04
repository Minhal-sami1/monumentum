#!/usr/bin/env bash
# make paper: regenerate metrics, then build the PDF from generated tables.
# Also greps the TeX source to PROVE no metric value is hard-coded: every
# number must arrive through \input{figures/metrics.tex} macros.
set -eu
PY_ARG="${1:?usage: build.sh <python>}"
case "$PY_ARG" in
  /*|[A-Za-z]:*) PY="$PY_ARG" ;;
  *) PY="$(pwd)/$PY_ARG" ;;
esac
HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. metrics must exist (make paper depends on reproduce)
test -f "$HERE/figures/metrics.tex" || { echo "missing figures/metrics.tex; run make reproduce"; exit 1; }

# 2. anti-hardcode guard: no bare metric-like number in the prose source.
#    numbers are allowed only in metrics.tex/metrics_table.tex (generated),
#    in section/figure references, and in citation years handled separately.
"$PY" "$HERE/check_no_hardcoded.py" "$HERE/monumentum-paper.tex"

# 3. build (tectonic is self-contained; falls back to latexmk/pdflatex)
cd "$HERE"
mkdir -p build
if command -v tectonic >/dev/null 2>&1; then
  tectonic -X compile monumentum-paper.tex --outdir build --keep-logs
elif command -v latexmk >/dev/null 2>&1; then
  latexmk -pdf -outdir=build monumentum-paper.tex
elif command -v pdflatex >/dev/null 2>&1; then
  mkdir -p build
  pdflatex -output-directory=build monumentum-paper.tex
  pdflatex -output-directory=build monumentum-paper.tex
else
  echo "no LaTeX engine found (tectonic/latexmk/pdflatex)"; exit 1
fi

test -f build/monumentum-paper.pdf
echo "paper: built paper/build/monumentum-paper.pdf"
