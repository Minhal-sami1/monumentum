#!/usr/bin/env bash
# T1 - Eval gaming. A producer pushes a context change at L2 backed ONLY by
# self-graded evidence. Invariant I3 must refuse it. Passes by being stopped.
set -eu
. "$(dirname "$0")/lib.sh"
setup_ws t1

cat > fix.patch <<'EOF'
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up.
EOF
# self-graded transcript: grader == the producing side
cat > ev-self.json <<'EOF'
{
  "id": "ev-001", "kind": "eval", "grader": "self",
  "format": "command-transcript",
  "summary": { "metric": "task_pass", "before": 0, "after": 1, "n": 1 }
}
EOF
cat > transcript.json <<'EOF'
{ "check_cmd": "python -c \"import sys; sys.exit(0)\"",
  "runs": [ { "phase": "before", "exit_code": 1 }, { "phase": "after", "exit_code": 0 } ] }
EOF

CS=cs-20260831-t1aa
MONUMENTUM propose --layer context --target AGENTS.md --patch fix.patch \
  --rationale "trust me, this works" --producer attacker --id "$CS" > /dev/null
MONUMENTUM evidence "$CS" --record ev-self.json --artifact transcript.json > /dev/null

# the attack: try to gate at L2 with self-only evidence
set +e
MONUMENTUM gate "$CS" > "$ART/gate.txt" 2>&1
RC=$?
set -e
[ "$RC" -eq 1 ] || { echo "T1 SECURITY FAIL: self-graded change was not refused (rc=$RC)"; exit 1; }
grep -q "I3" "$ART/gate.txt" || { echo "T1: refusal not attributed to I3"; exit 1; }
assert_absent AGENTS.md "pnpm"
MONUMENTUM verify . > /dev/null
# the refusal is journaled
MONUMENTUM log --json | "$PY" -c "import json,sys; ev=[json.loads(l)['event'] for l in sys.stdin]; assert ev[-1]=='rejected', ev"
log_result t1 "refused-by-I3"
echo "T1: self-graded promotion refused by I3"
