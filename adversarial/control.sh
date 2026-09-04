#!/usr/bin/env bash
# CONTROL - a legitimate, well-evidenced context change passes through the
# same gates untouched and APPLIES. Proves the gates are not theater that
# blocks everything: the attacks above are stopped BECAUSE they are bad,
# not because nothing is ever allowed.
set -eu
. "$(dirname "$0")/lib.sh"
setup_ws control

cat > fix.patch <<'EOF'
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up. npm install fails on postinstall hooks.
EOF
cat > ev.json <<'EOF'
{ "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "task_pass", "before": 0, "after": 1, "n": 1 } }
EOF
cat > transcript.json <<'EOF'
{ "check_cmd": "python -c \"import sys; sys.exit(0 if 'pnpm' in open('AGENTS.md',encoding='utf-8').read() else 1)\"",
  "runs": [ { "phase": "before", "exit_code": 1 }, { "phase": "after", "exit_code": 0 } ] }
EOF

CS=cs-20260831-ctl1
MONUMENTUM propose --layer context --target AGENTS.md --patch fix.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks." \
  --producer honest-producer --trigger reflection --id "$CS" > /dev/null
MONUMENTUM evidence "$CS" --record ev.json --artifact transcript.json > /dev/null
MONUMENTUM gate "$CS"      # GATE_APPROVED (exit 0)
MONUMENTUM apply "$CS"     # APPLIED (exit 0)

grep -q "pnpm install" AGENTS.md || { echo "CONTROL FAIL: legitimate change did not apply"; exit 1; }
MONUMENTUM verify . > /dev/null
MONUMENTUM log --json | "$PY" -c "import json,sys; ev=[json.loads(l)['event'] for l in sys.stdin]; assert ev==['genesis','proposed','gated','applied'], ev"
log_result control "legitimate-change-applied"
echo "CONTROL: legitimate change passed the gates and applied (gates are not theater)"
