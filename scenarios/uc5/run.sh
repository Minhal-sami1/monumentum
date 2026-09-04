#!/usr/bin/env bash
# UC5 - Audit reconstruction. After a UC1-UC4-style history, a script
# answers "why does this workspace behave this way today?" from the
# journal ALONE (no git log, no source diffs) - and the answer matches
# reality.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
MONUMENTUM() { "$PY" -m monumentum.cli "$@"; }
RUN_ID="uc5-$(date -u +%Y%m%d-%H%M%S)-$$"
T_START=$("$PY" -c "import time; print(time.time())")

WORK="$DIR/out/work"
ART="$DIR/out/artifacts"
rm -rf "$DIR/out"; mkdir -p "$WORK" "$ART"

# fixture: the UC4 project plus the UC1 AGENTS.md
cp -r "$REPO_ROOT/scenarios/uc4/fixture/." "$WORK/"
cp "$REPO_ROOT/scenarios/uc1/fixture/AGENTS.md" "$WORK/AGENTS.md"
cp "$REPO_ROOT/scenarios/uc1/fixture/install.js" "$WORK/install.js"
cd "$WORK"

MONUMENTUM init --policy monumentum-policy.yaml > /dev/null

make_patch() {
  "$PY" - "$1" "$2" "$3" "$4" <<'EOF'
import difflib, sys
old = open(sys.argv[1], encoding="utf-8").readlines()
new = open(sys.argv[2], encoding="utf-8").readlines()
rel = sys.argv[4]
with open(sys.argv[3], "w", encoding="utf-8", newline="") as f:
    f.writelines(difflib.unified_diff(old, new, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
EOF
}

cat > ev.json <<'EOF'
{
  "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "check_pass", "before": 0, "after": 1, "n": 1 }
}
EOF

# --- history 1 (UC1-style): context lesson, survives ---------------------------
cat > fix.patch <<'EOF'
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up. npm install fails on postinstall hooks.
EOF
cat > transcript1.json <<'EOF'
{
  "check_cmd": "node install.js pnpm",
  "runs": [ { "phase": "before", "exit_code": 1 }, { "phase": "after", "exit_code": 0 } ]
}
EOF
CS_A=cs-20260831-uc5a
MONUMENTUM propose --layer context --target AGENTS.md --patch fix.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks." \
  --producer claude-code-scripted --trigger reflection --id "$CS_A" > /dev/null
MONUMENTUM evidence "$CS_A" --record ev.json --artifact transcript1.json > /dev/null
MONUMENTUM gate "$CS_A" > /dev/null
MONUMENTUM apply "$CS_A" > /dev/null

# --- history 2 (UC4-style): capability change applied then rolled back ----------
cat > transcript2.json <<EOF
{
  "check_cmd": "\"$PY\" -c \"import sys; sys.path.insert(0,'.'); from tools.textutil import slugify; sys.exit(0 if slugify('Hello World')=='hello-world' else 1)\"",
  "runs": [ { "phase": "before", "exit_code": 0 }, { "phase": "after", "exit_code": 0 } ]
}
EOF
make_patch tools/textutil.py variant1.py.txt bad.patch tools/textutil.py
CS_B=cs-20260831-uc5b
MONUMENTUM propose --layer capability --target tools/textutil.py --patch bad.patch \
  --rationale "Simplify slugify with one regex; micro-benchmark 3x faster." \
  --producer optimizer-bot --id "$CS_B" > /dev/null
MONUMENTUM evidence "$CS_B" --record ev.json --artifact transcript2.json > /dev/null
MONUMENTUM gate "$CS_B" > /dev/null
MONUMENTUM apply "$CS_B" > /dev/null
set +e
"$PY" -m pytest test_textutil.py -q > "$ART/regression.log" 2>&1
set -e
MONUMENTUM rollback "$CS_B" --actor human/operator > /dev/null

# --- history 3 (UC4-style): a good capability change, survives ------------------
make_patch tools/textutil.py variant3.py.txt good.patch tools/textutil.py
CS_C=cs-20260831-uc5c
MONUMENTUM propose --layer capability --target tools/textutil.py --patch good.patch \
  --rationale "Treat dots as separators; matches slug policy for filenames." \
  --producer optimizer-bot --id "$CS_C" > /dev/null
MONUMENTUM evidence "$CS_C" --record ev.json --artifact transcript2.json > /dev/null
MONUMENTUM gate "$CS_C" > /dev/null
MONUMENTUM apply "$CS_C" > /dev/null

# --- history 4 (UC2-reject-style): out-of-allowlist proposal refused -------------
cat > sneaky.patch <<'EOF'
--- a/src/secrets.py
+++ b/src/secrets.py
@@ -0,0 +1 @@
+TOKEN = "..."
EOF
CS_D=cs-20260831-uc5d
set +e
MONUMENTUM propose --layer context --target src/secrets.py --patch sneaky.patch \
  --rationale "store the token where every session can see it" \
  --producer claude-code-scripted --id "$CS_D" > /dev/null 2>&1
[ $? -eq 1 ] || { echo "expected rejection"; exit 1; }
set -e

# --- the audit -------------------------------------------------------------------
"$PY" "$DIR/audit.py" . > "$ART/audit-report.txt"
cat "$ART/audit-report.txt"

grep -q "AUDIT OK" "$ART/audit-report.txt"
grep -q "$CS_A" "$ART/audit-report.txt"
grep -q "Repo uses pnpm" "$ART/audit-report.txt"          # rationale from journal alone
grep -q "rolled back by human/operator" "$ART/audit-report.txt"
grep -q "$CS_D" "$ART/audit-report.txt"                   # the refusal is explained
grep -q "matches no targets_allow" "$ART/audit-report.txt"

MONUMENTUM verify .
cp .monumentum/journal/*.ndjson "$ART/journal.ndjson"

T_END=$("$PY" -c "import time; print(time.time())")
mkdir -p "$REPO_ROOT/experiments/scenarios/logs"
"$PY" - "$RUN_ID" "$T_START" "$T_END" <<'EOF'
import json, os, sys
rec = {"run_id": sys.argv[1], "experiment": "scenario-uc5",
       "seconds": round(float(sys.argv[3]) - float(sys.argv[2]), 3),
       "audit_sources": ["journal"], "ok": True}
path = os.path.join(os.environ["REPO_ROOT"], "experiments", "scenarios", "logs",
                    sys.argv[1] + ".jsonl")
open(path, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
EOF
echo "UC5 ok (run $RUN_ID)"
