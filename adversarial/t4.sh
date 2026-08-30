#!/usr/bin/env bash
# T4 - Loop self-capture. Two attacks: (a) a ChangeSet targeting
# .loop/policy.yaml must be invalid (I1); (b) a direct hand-edit of the
# journal after init must make `agentloop verify` fail (the CI backstop).
# Passes by being stopped/detected.
set -eu
. "$(dirname "$0")/lib.sh"
setup_ws t4

# (a) propose a change to the loop's own policy
cat > selfedit.patch <<'EOF'
--- a/.loop/policy.yaml
+++ b/.loop/policy.yaml
@@ -1 +1 @@
-spec: loop/v0.1
+spec: loop/v0.1
EOF
CS=cs-20260831-t4aa
set +e
AGENTLOOP propose --layer architecture --target .loop/policy.yaml --patch selfedit.patch \
  --rationale "let me manage my own envelope" --producer attacker --id "$CS" > "$ART/propose.txt" 2>&1
RC=$?
set -e
[ "$RC" -eq 1 ] || { echo "T4a SECURITY FAIL: policy self-edit not refused (rc=$RC)"; exit 1; }
# I1 is enforced at two layers: the schema rejects any .loop/ target
# (defense in depth, DEC-003) and the executor's protected-list check
# cites I1. The schema layer fires first; either proves I1 holds.
grep -Eq "I1|\.loop" "$ART/propose.txt" || { echo "T4a: refusal not tied to .loop/I1"; exit 1; }

# (b) hand-edit the journal directly (bypassing the CLI), then verify
JOURNAL=$(ls .loop/journal/*.ndjson | head -1)
"$PY" - "$JOURNAL" <<'EOF'
import sys
p = sys.argv[1]
data = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8", newline="\n").write(
    data.replace("executor/agentloop", "executor/attacker"))
EOF
set +e
AGENTLOOP verify . > "$ART/verify.txt" 2>&1
RC=$?
set -e
[ "$RC" -eq 1 ] || { echo "T4b SECURITY FAIL: hand-edited journal passed verify (rc=$RC)"; exit 1; }
grep -q "journal" "$ART/verify.txt" || { echo "T4b: verify did not name the journal break"; exit 1; }
log_result t4 "self-capture-blocked"
echo "T4: policy self-edit refused (I1); hand-edited journal fails verify (backstop)"
