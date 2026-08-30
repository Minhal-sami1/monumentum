#!/usr/bin/env bash
# Run every adversarial test. Each script performs a REAL attack against
# the real binary and exits 0 only if the system stopped or detected it.
set -u
PY_ARG="${1:?usage: run_all.sh <python-interpreter>}"
case "$PY_ARG" in
  /*|[A-Za-z]:*) PY="$PY_ARG" ;;
  *) PY="$(pwd)/$PY_ARG" ;;
esac
export PY
export REPO_ROOT="$(pwd)"

failures=0
count=0
for script in adversarial/t*.sh adversarial/control.sh; do
  [ -f "$script" ] || continue
  count=$((count + 1))
  name="$(basename "$script" .sh)"
  echo "=== adversarial $name ==="
  if bash "$script"; then
    echo "PASS $name (attack stopped/detected)"
  else
    echo "FAIL $name"
    failures=$((failures + 1))
  fi
done

echo "adversarial: $((count - failures))/$count passed"
[ "$count" -gt 0 ] && [ "$failures" -eq 0 ]
