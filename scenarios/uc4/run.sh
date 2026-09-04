#!/usr/bin/env bash
# UC4 - Regression + ratchet-down. Applied changes break a REAL test inside
# the observation window. Detection, one-command rollback to exact prior
# hashes, and automatic de-escalation - the ratchet also turns down.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
MONUMENTUM() { "$PY" -m monumentum.cli "$@"; }
RUN_ID="uc4-$(date -u +%Y%m%d-%H%M%S)-$$"
T_START=$("$PY" -c "import time; print(time.time())")

WORK="$DIR/out/work"
ART="$DIR/out/artifacts"
rm -rf "$DIR/out"; mkdir -p "$WORK" "$ART"
cp -r "$DIR/fixture/." "$WORK/"
cd "$WORK"

MONUMENTUM init --policy monumentum-policy.yaml > /dev/null

# the real test suite passes at the start
"$PY" -m pytest test_textutil.py -q > "$ART/tests-baseline.log" 2>&1

HASH0=$("$PY" -c "
from monumentum.hashing import sha256_file
print(sha256_file(__import__('pathlib').Path('tools/textutil.py')))")

make_patch() { # old new out
  "$PY" - "$1" "$2" "$3" <<'EOF'
import difflib, sys
old = open(sys.argv[1], encoding="utf-8").readlines()
new = open(sys.argv[2], encoding="utf-8").readlines()
rel = "tools/textutil.py"
with open(sys.argv[3], "w", encoding="utf-8", newline="") as f:
    f.writelines(difflib.unified_diff(old, new, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
EOF
}

cat > ev.json <<'EOF'
{
  "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "spot_check_pass", "before": 1, "after": 1, "n": 1 }
}
EOF
cat > transcript.json <<EOF
{
  "check_cmd": "\"$PY\" -c \"import sys; sys.path.insert(0,'.'); from tools.textutil import slugify; sys.exit(0 if slugify('Hello World')=='hello-world' else 1)\"",
  "runs": [ { "phase": "before", "exit_code": 0 }, { "phase": "after", "exit_code": 0 } ]
}
EOF

apply_bad_change() { # cs-id variant-file rationale
  local CS="$1" VARIANT="$2" WHY="$3"
  make_patch tools/textutil.py "$VARIANT" change.patch
  MONUMENTUM propose --layer capability --target tools/textutil.py --patch change.patch \
    --rationale "$WHY" --producer optimizer-bot --trigger optimization --id "$CS" > /dev/null
  MONUMENTUM evidence "$CS" --record ev.json --artifact transcript.json > /dev/null
  MONUMENTUM gate "$CS" > /dev/null      # L2 auto: evidence verified, I3 satisfied
  MONUMENTUM apply "$CS" > /dev/null
}

detect_and_rollback() { # cs-id logfile
  local CS="$1" LOG="$2"
  set +e
  "$PY" -m pytest test_textutil.py -q > "$LOG" 2>&1   # the observation window
  local TEST_EXIT=$?
  set -e
  [ "$TEST_EXIT" -ne 0 ] || { echo "expected the real test suite to catch the regression"; exit 1; }
  MONUMENTUM rollback "$CS" --actor human/operator > /dev/null
  local NOW
  NOW=$("$PY" -c "
from monumentum.hashing import sha256_file
print(sha256_file(__import__('pathlib').Path('tools/textutil.py')))")
  [ "$NOW" = "$HASH0" ] || { echo "rollback did not restore exact prior hash"; exit 1; }
  "$PY" -m pytest test_textutil.py -q >> "$LOG" 2>&1   # green again after rollback
}

# --- regression 1: plausible regex "optimization" breaks unicode + apostrophes
apply_bad_change cs-20260831-uc4a "$WORK/variant1.py.txt" \
  "Simplify slugify with one regex; micro-benchmark 3x faster."
detect_and_rollback cs-20260831-uc4a "$ART/regression1.log"

# --- regression 2: split/join rewrite drops punctuation handling ---------------
apply_bad_change cs-20260831-uc4b "$WORK/variant2.py.txt" \
  "Replace char loop with split/join; shorter and faster."
detect_and_rollback cs-20260831-uc4b "$ART/regression2.log"

# --- the ratchet turned down: capability is now L1 ------------------------------
grep -q '"capability": "L1"' .monumentum/state.json || { echo "de-escalation missing"; exit 1; }

# a third change now QUEUES instead of auto-applying
make_patch tools/textutil.py "$WORK/variant3.py.txt" change3.patch
CS3=cs-20260831-uc4c
MONUMENTUM propose --layer capability --target tools/textutil.py --patch change3.patch \
  --rationale "Treat dots as separators too." --producer optimizer-bot --id "$CS3" > /dev/null
MONUMENTUM evidence "$CS3" --record ev.json --artifact transcript.json > /dev/null
set +e
MONUMENTUM gate "$CS3" > /dev/null
GATE_EXIT=$?
set -e
[ "$GATE_EXIT" -eq 2 ] || { echo "expected QUEUED after de-escalation, got $GATE_EXIT"; exit 1; }

# --- asserts ---------------------------------------------------------------------
MONUMENTUM verify .
MONUMENTUM log --json > "$ART/journal.jsonl"
"$PY" - "$ART/journal.jsonl" <<'EOF'
import json, sys
entries = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
events = [e["event"] for e in entries]
assert events == ["genesis",
                  "proposed", "gated", "applied", "rolled_back",
                  "proposed", "gated", "applied", "rolled_back", "policy_changed",
                  "proposed", "gated"], events
pc = [e for e in entries if e["event"] == "policy_changed"][0]
assert "L2 -> L1" in pc["decision"]["reason"], pc
assert pc["decision"]["gate"] == "de_escalation"
EOF

cp .monumentum/state.json "$ART/state.json"
T_END=$("$PY" -c "import time; print(time.time())")
mkdir -p "$REPO_ROOT/experiments/scenarios/logs"
"$PY" - "$RUN_ID" "$T_START" "$T_END" <<'EOF'
import json, os, sys
rec = {"run_id": sys.argv[1], "experiment": "scenario-uc4",
       "seconds": round(float(sys.argv[3]) - float(sys.argv[2]), 3),
       "rollbacks": 2, "de_escalated": "capability L2->L1", "ok": True}
path = os.path.join(os.environ["REPO_ROOT"], "experiments", "scenarios", "logs",
                    sys.argv[1] + ".jsonl")
open(path, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
EOF
echo "UC4 ok (run $RUN_ID)"
