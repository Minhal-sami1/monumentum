#!/usr/bin/env bash
# UC1 - Context lesson. npm postinstall fails, pnpm works. The producer
# learns it, proposes an AGENTS.md diff with a fail->apply->pass command
# transcript, and the L2 gate auto-applies it with independent evidence.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
MONUMENTUM() { "$PY" -m monumentum.cli "$@"; }
RUN_ID="uc1-$(date -u +%Y%m%d-%H%M%S)-$$"
T_START=$("$PY" -c "import time; print(time.time())")

WORK="$DIR/out/work"
ART="$DIR/out/artifacts"
rm -rf "$DIR/out"; mkdir -p "$WORK" "$ART"
cp -r "$DIR/fixture/." "$WORK/"
cd "$WORK"

MONUMENTUM init > "$ART/init.txt"

# --- the producer hits the failure (real command, real exit code) ---------
set +e
node install.js npm > "$ART/npm-fail.log" 2>&1
NPM_EXIT=$?
set -e
[ "$NPM_EXIT" -ne 0 ] || { echo "expected npm path to fail"; exit 1; }
node install.js pnpm >> "$ART/npm-fail.log" 2>&1   # the discovered fix works

# --- the producer proposes the lesson --------------------------------------
cat > fix.patch <<'EOF'
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up. npm install fails on postinstall hooks.
EOF

cat > transcript.json <<'EOF'
{
  "check_cmd": "node install.js pnpm",
  "runs": [
    { "phase": "before", "cmd": "node install.js npm", "exit_code": 1 },
    { "phase": "after", "cmd": "node install.js pnpm", "exit_code": 0 }
  ]
}
EOF

cat > ev.json <<'EOF'
{
  "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "postinstall_pass", "before": 0, "after": 1, "n": 1 }
}
EOF

CS=cs-20260831-uc1a
MONUMENTUM propose --layer context --target AGENTS.md --patch fix.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks." \
  --producer claude-code-scripted --trigger reflection --id "$CS" > "$ART/propose.txt"
MONUMENTUM evidence "$CS" --record ev.json --artifact transcript.json
MONUMENTUM gate "$CS"
MONUMENTUM apply "$CS"

# --- asserts ----------------------------------------------------------------
grep -q "pnpm install" AGENTS.md || { echo "lesson missing from AGENTS.md"; exit 1; }
MONUMENTUM verify .
MONUMENTUM log --json > "$ART/journal.jsonl"
"$PY" - "$ART/journal.jsonl" <<'EOF'
import json, sys
events = [json.loads(l)["event"] for l in open(sys.argv[1], encoding="utf-8")]
assert events == ["genesis", "proposed", "gated", "applied"], events
EOF

# --- next session benefits ---------------------------------------------------
# a fresh "session" reads AGENTS.md, follows the lesson, and succeeds
NEXT_CMD=$(grep -o "pnpm install" AGENTS.md | head -1)
[ "$NEXT_CMD" = "pnpm install" ]
node install.js pnpm > "$ART/next-session.log" 2>&1

cp .monumentum/state.json "$ART/state.json"
T_END=$("$PY" -c "import time; print(time.time())")
mkdir -p "$REPO_ROOT/experiments/scenarios/logs"
"$PY" - "$RUN_ID" "$T_START" "$T_END" <<'EOF'
import json, os, sys
run_id, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
rec = {"run_id": run_id, "experiment": "scenario-uc1", "seconds": round(t1 - t0, 3),
       "events": ["genesis", "proposed", "gated", "applied"], "ok": True}
path = os.path.join(os.environ["REPO_ROOT"], "experiments", "scenarios", "logs", run_id + ".jsonl")
open(path, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
EOF
echo "UC1 ok (run $RUN_ID)"
