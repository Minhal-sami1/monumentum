#!/usr/bin/env bash
# make reproduce: re-run every experiment from clean logs, then aggregate
# into the paper's tables and figures. Deterministic experiments always run;
# the live-model trigger experiment runs only when --with-trigger is passed
# (it needs the claude CLI + API and records honestly when quota-blocked).
set -eu
PY_ARG="${1:?usage: reproduce.sh <python> [--with-trigger] [--n N]}"
shift || true
case "$PY_ARG" in
  /*|[A-Za-z]:*) PY="$PY_ARG" ;;
  *) PY="$(pwd)/$PY_ARG" ;;
esac
export PY
export REPO_ROOT="$(pwd)"

WITH_TRIGGER=0
TRIGGER_N=5
while [ $# -gt 0 ]; do
  case "$1" in
    --with-trigger) WITH_TRIGGER=1 ;;
    --n) shift; TRIGGER_N="$1" ;;
  esac
  shift
done

echo "## clearing old run logs"
rm -rf experiments/*/logs
mkdir -p experiments/interop/logs experiments/scenarios/logs experiments/adversarial/logs \
         experiments/overhead/logs experiments/evidence/logs experiments/trigger/logs

echo "## interop demo"
"$PY" demo/run_demo.py

echo "## scenarios (UC1-UC5)"
bash scenarios/run_all.sh "$PY"

echo "## adversarial suite"
bash adversarial/run_all.sh "$PY"

echo "## deterministic experiments (overhead, evidence)"
"$PY" experiments/experiments.py

if [ "$WITH_TRIGGER" -eq 1 ]; then
  echo "## trigger experiment (live model, n=$TRIGGER_N)"
  "$PY" experiments/trigger/run_trigger.py --n "$TRIGGER_N" || \
    echo "trigger experiment did not complete; metrics will report it honestly"
else
  echo "## trigger experiment skipped (pass --with-trigger to run the live-model B1 metric)"
fi

echo "## aggregating metrics -> paper/figures"
"$PY" experiments/metrics.py

echo "reproduce: done"
