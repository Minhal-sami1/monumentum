#!/usr/bin/env bash
# Doc-test for docs/QUICKSTART.md: runs the exact consumer path end to end
# against the real CLI and asserts each step's outcome. No live model.
# Part of `make verify` (the final gate).
set -eu
PY_ARG="${1:?usage: quickstart_test.sh <python>}"
case "$PY_ARG" in
  /*|[A-Za-z]:*) PY="$PY_ARG" ;;
  *) PY="$(pwd)/$PY_ARG" ;;
esac
AGENTLOOP() { "$PY" -m agentloop.cli "$@"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

# a project with AGENTS.md (step 1 precondition)
printf '# Agent notes\n\nUse npm install to set up.\n' > AGENTS.md

# step 1: govern
AGENTLOOP init > init.txt
grep -q "Initialized .loop/" init.txt
test -f .loop/policy.yaml
grep -q "agentloop:managed:begin" AGENTS.md   # step B2: managed block appended

# step 2: the diff (exactly as in QUICKSTART.md)
cat > lesson.patch <<'EOF'
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1,3 +1,3 @@
 # Agent notes

-Use npm install to set up.
+Use pnpm install to set up. npm install fails on postinstall hooks.
EOF

# step 3: propose
OUT=$(AGENTLOOP propose --layer context --target AGENTS.md --patch lesson.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks." --producer me)
CS=$(printf '%s' "$OUT" | grep -o 'cs-[0-9]\{8\}-[a-z0-9]*' | head -1)
test -n "$CS"

# step 4: evidence
cat > transcript.json <<'EOF'
{ "check_cmd": "grep -q 'pnpm install' AGENTS.md",
  "runs": [ { "phase": "before", "exit_code": 1 }, { "phase": "after", "exit_code": 0 } ] }
EOF
cat > ev.json <<'EOF'
{ "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "task_pass", "before": 0, "after": 1, "n": 1 } }
EOF
AGENTLOOP evidence "$CS" --record ev.json --artifact transcript.json > /dev/null

# step 5: gate + apply
AGENTLOOP gate "$CS" | grep -q GATE_APPROVED
AGENTLOOP apply "$CS" | grep -q APPLIED
grep -q "pnpm install" AGENTS.md

# step 6: audit + undo
AGENTLOOP log | grep -q applied
AGENTLOOP verify . | grep -q "verify OK"
AGENTLOOP rollback "$CS" > /dev/null
grep -q "Use npm install to set up." AGENTS.md
! grep -q "pnpm install" AGENTS.md
AGENTLOOP verify . | grep -q "verify OK"

# step 7: install-skill
AGENTLOOP install-skill > /dev/null
test -f .claude/skills/loop/SKILL.md
test -f .claude/hooks/pretooluse_guard.py

echo "quickstart-test: OK"
