#!/usr/bin/env bash
# T6 - Journal tampering. After a real applied change, edit a PAST journal
# line. Verification must fail and name the exact broken entry. Passes by
# detection.
set -eu
. "$(dirname "$0")/lib.sh"
setup_ws t6

cat > fix.patch <<'EOF'
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up.
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

CS=cs-20260831-t6aa
MONUMENTUM propose --layer context --target AGENTS.md --patch fix.patch \
  --rationale "Repo uses pnpm." --producer producer --id "$CS" > /dev/null
MONUMENTUM evidence "$CS" --record ev.json --artifact transcript.json > /dev/null
MONUMENTUM gate "$CS" > /dev/null
MONUMENTUM apply "$CS" > /dev/null
MONUMENTUM verify . > /dev/null   # clean before tampering

# tamper with a PAST entry (the applied entry's decision reason)
JOURNAL=$(ls .monumentum/journal/*.ndjson | head -1)
"$PY" - "$JOURNAL" <<'EOF'
import sys
p = sys.argv[1]
lines = open(p, encoding="utf-8").read().splitlines()
# corrupt the 'proposed' entry (seq 1): change its rationale note
lines[1] = lines[1].replace("Repo uses pnpm.", "Repo uses npm.")
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
EOF

set +e
MONUMENTUM verify . > "$ART/verify.txt" 2>&1
RC=$?
set -e
[ "$RC" -eq 1 ] || { echo "T6 SECURITY FAIL: tampered journal passed verify (rc=$RC)"; exit 1; }
grep -qi "seq 2\|hash chain broken\|not in canonical" "$ART/verify.txt" \
  || { echo "T6: verify did not pinpoint the break"; cat "$ART/verify.txt"; exit 1; }
log_result t6 "tamper-detected"
echo "T6: journal tampering detected by verify at the break point"
