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
# Timing metrics are reported as means, so they must never be a mean of one
# sample. Repeat the experiments that produce timings.
TIMING_REPEATS="${TIMING_REPEATS:-3}"
while [ $# -gt 0 ]; do
  case "$1" in
    --with-trigger) WITH_TRIGGER=1 ;;
    --n) shift; TRIGGER_N="$1" ;;
    --timing-repeats) shift; TIMING_REPEATS="$1" ;;
  esac
  shift
done

echo "## clearing old run logs"
rm -rf experiments/*/logs
mkdir -p experiments/interop/logs experiments/scenarios/logs experiments/adversarial/logs \
         experiments/overhead/logs experiments/evidence/logs experiments/trigger/logs

echo "## interop demo (x$TIMING_REPEATS for the lesson-to-second-runtime mean)"
i=1
while [ "$i" -le "$TIMING_REPEATS" ]; do
  "$PY" demo/run_demo.py
  i=$((i + 1))
done

echo "## scenarios (UC1-UC5)"
bash scenarios/run_all.sh "$PY"

# UC3 carries the fleet-propagation timing; repeat it for the same reason.
echo "## UC3 repeats (x$((TIMING_REPEATS - 1)) more, for the propagation mean)"
i=2
while [ "$i" -le "$TIMING_REPEATS" ]; do
  bash scenarios/uc3/run.sh
  i=$((i + 1))
done

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
