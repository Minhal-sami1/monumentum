#!/usr/bin/env bash
# Run every battle-test scenario headless. Usage: run_all.sh <python>
set -u
PY_ARG="${1:?usage: run_all.sh <python-interpreter>}"

# resolve the interpreter to an absolute path (scenarios cd around)
case "$PY_ARG" in
  /*|[A-Za-z]:*) PY="$PY_ARG" ;;
  *) PY="$(pwd)/$PY_ARG" ;;
esac
export PY
export REPO_ROOT="$(pwd)"

failures=0
count=0
for script in scenarios/uc*/run.sh; do
  [ -f "$script" ] || continue
  count=$((count + 1))
  name="$(basename "$(dirname "$script")")"
  echo "=== scenario $name ==="
  if bash "$script"; then
    echo "PASS $name"
  else
    echo "FAIL $name"
    failures=$((failures + 1))
  fi
done

echo "scenarios: $((count - failures))/$count passed"
[ "$count" -gt 0 ] && [ "$failures" -eq 0 ]
