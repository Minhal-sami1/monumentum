#!/usr/bin/env bash
# UC2 - Capability repair. A bundled skill script is broken; the producer
# proposes the fix. The L1 queue is honored (no apply before approval).
# BOTH reviewer paths run: approve (applies) and reject (never applies).
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTLOOP() { "$PY" -m agentloop.cli "$@"; }
RUN_ID="uc2-$(date -u +%Y%m%d-%H%M%S)-$$"
T_START=$("$PY" -c "import time; print(time.time())")

WORK="$DIR/out/work"
ART="$DIR/out/artifacts"
rm -rf "$DIR/out"; mkdir -p "$WORK" "$ART"
cp -r "$DIR/fixture/." "$WORK/"
cd "$WORK"

AGENTLOOP init > "$ART/init.txt"
SCRIPT=".claude/skills/fix-lint/scripts/check.py"

# --- reproduce the breakage (real command) ----------------------------------
set +e
"$PY" "$SCRIPT" > "$ART/broken.log" 2>&1
BROKEN_EXIT=$?
set -e
[ "$BROKEN_EXIT" -ne 0 ] || { echo "expected the skill script to be broken"; exit 1; }

# --- the producer proposes the repair ----------------------------------------
cat > fix.patch <<'EOF'
--- a/.claude/skills/fix-lint/scripts/check.py
+++ b/.claude/skills/fix-lint/scripts/check.py
@@ -12,7 +12,6 @@


 def main():
-    # the helper was renamed to count_todos, this call is stale
-    total = sys.modules[__name__].count_todo_items("TODO: one\nTODO: two\n")
+    total = count_todos("TODO: one\nTODO: two\n")
     print(f"todos: {total}")
     return 0
EOF

cat > transcript.json <<EOF
{
  "check_cmd": "\"$PY\" $SCRIPT",
  "runs": [
    { "phase": "before", "exit_code": 1 },
    { "phase": "after", "exit_code": 0 }
  ]
}
EOF

cat > ev.json <<'EOF'
{
  "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "skill_script_pass", "before": 0, "after": 1, "n": 1 }
}
EOF

CS=cs-20260831-uc2a
AGENTLOOP propose --layer capability --target "$SCRIPT" --patch fix.patch \
  --rationale "fix-lint script calls the pre-refactor helper name; rename to count_todos." \
  --producer claude-code-scripted --trigger user-correction --id "$CS" > "$ART/propose.txt"
AGENTLOOP evidence "$CS" --record ev.json --artifact transcript.json

# --- L1 queue honored ---------------------------------------------------------
set +e
AGENTLOOP gate "$CS"
GATE_EXIT=$?
set -e
[ "$GATE_EXIT" -eq 2 ] || { echo "expected queue exit 2, got $GATE_EXIT"; exit 1; }

set +e
"$PY" "$SCRIPT" > /dev/null 2>&1
STILL_BROKEN=$?
AGENTLOOP apply "$CS" > /dev/null 2>&1
APPLY_EXIT=$?
set -e
[ "$STILL_BROKEN" -ne 0 ] || { echo "target changed before approval"; exit 1; }
[ "$APPLY_EXIT" -ne 0 ] || { echo "apply must refuse a queued changeset"; exit 1; }

# --- reviewer approves: applied ------------------------------------------------
AGENTLOOP approve "$CS" --actor reviewer/minhal
"$PY" "$SCRIPT" > "$ART/fixed.log" 2>&1
grep -q "todos: 2" "$ART/fixed.log"

# --- reject path: a second (unwanted) change never applies ---------------------
cat > riskier.patch <<'EOF'
--- a/.claude/skills/fix-lint/SKILL.md
+++ b/.claude/skills/fix-lint/SKILL.md
@@ -4,4 +4,4 @@
 ---

-Run `python .claude/skills/fix-lint/scripts/check.py` and report its output.
+Run the checker with elevated permissions and auto-fix everything silently.
EOF
CS2=cs-20260831-uc2b
AGENTLOOP propose --layer capability --target .claude/skills/fix-lint/SKILL.md \
  --patch riskier.patch --rationale "make the skill fix things automatically" \
  --producer claude-code-scripted --id "$CS2" > /dev/null
AGENTLOOP evidence "$CS2" --record ev.json --artifact transcript.json
set +e
AGENTLOOP gate "$CS2"; [ $? -eq 2 ] || { echo "cs2 should queue"; exit 1; }
set -e
AGENTLOOP reject "$CS2" --actor reviewer/minhal --reason "silent auto-fix is not acceptable"
grep -q "report its output" .claude/skills/fix-lint/SKILL.md || { echo "reject modified the file"; exit 1; }

# --- asserts -------------------------------------------------------------------
AGENTLOOP verify .
AGENTLOOP log --json > "$ART/journal.jsonl"
"$PY" - "$ART/journal.jsonl" <<'EOF'
import json, sys
entries = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
events = [e["event"] for e in entries]
assert events == ["genesis", "proposed", "gated", "approved", "applied",
                  "proposed", "gated", "rejected"], events
approved = [e for e in entries if e["event"] == "approved"][0]
assert approved["actor"] == "reviewer/minhal"
rejected = [e for e in entries if e["event"] == "rejected"][0]
assert rejected["actor"] == "reviewer/minhal"
EOF

cp .loop/state.json "$ART/state.json"
T_END=$("$PY" -c "import time; print(time.time())")
mkdir -p "$REPO_ROOT/experiments/scenarios/logs"
"$PY" - "$RUN_ID" "$T_START" "$T_END" <<'EOF'
import json, os, sys
run_id, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
rec = {"run_id": run_id, "experiment": "scenario-uc2", "seconds": round(t1 - t0, 3),
       "approve_path": True, "reject_path": True, "ok": True}
path = os.path.join(os.environ["REPO_ROOT"], "experiments", "scenarios", "logs", run_id + ".jsonl")
open(path, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
EOF
echo "UC2 ok (run $RUN_ID)"
