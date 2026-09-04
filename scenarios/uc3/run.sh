#!/usr/bin/env bash
# UC3 - Fleet propagation. Workspaces A and B share a git-remote registry.
# A lesson lands in A; B receives it via sync, gates it LOCALLY, applies it.
# Propagation time is logged. A policy-violating pulled change is refused in B.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
MONUMENTUM() { "$PY" -m monumentum.cli "$@"; }
RUN_ID="uc3-$(date -u +%Y%m%d-%H%M%S)-$$"

WORK="$DIR/out/work"
ART="$DIR/out/artifacts"
rm -rf "$DIR/out"; mkdir -p "$WORK" "$ART"

# --- shared registry: a plain bare git remote --------------------------------
REG="$WORK/registry.git"
mkdir -p "$REG"
git -C "$REG" init --bare -b main -q

# --- workspace A ---------------------------------------------------------------
A="$WORK/a"; mkdir -p "$A"
cp "$REPO_ROOT/scenarios/uc1/fixture/AGENTS.md" "$A/AGENTS.md"
cp "$REPO_ROOT/scenarios/uc1/fixture/install.js" "$A/install.js"
cd "$A"
MONUMENTUM init --policy "$DIR/fixture/a-policy.yaml" > /dev/null
MONUMENTUM keygen --name producer-a > /dev/null
cat > .monumentum/registry.yaml <<EOF
spec: monumentum/v0.1
kind: git-remote
remote: { url: "$(cd "$REG" && pwd -W 2>/dev/null || pwd)", branch: main }
verify: { require_signatures: true, pubkeys_dir: pubkeys }
signing: { key_file: keys/producer-a.key, signer: producer-a }
EOF
mkdir -p .monumentum/pubkeys
cp .monumentum/keys/producer-a.pub .monumentum/pubkeys/

T0=$("$PY" -c "import time; print(time.time())")

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
  "runs": [ { "phase": "before", "exit_code": 1 }, { "phase": "after", "exit_code": 0 } ]
}
EOF
cat > ev.json <<'EOF'
{
  "id": "ev-001", "kind": "eval", "grader": "independent",
  "format": "command-transcript",
  "summary": { "metric": "postinstall_pass", "before": 0, "after": 1, "n": 1 }
}
EOF
CS=cs-20260831-uc3a
MONUMENTUM propose --layer context --target AGENTS.md --patch fix.patch \
  --rationale "Repo uses pnpm. npm install fails on postinstall hooks." \
  --producer producer-a --trigger reflection --id "$CS" > /dev/null
MONUMENTUM evidence "$CS" --record ev.json --artifact transcript.json > /dev/null
MONUMENTUM gate "$CS" > /dev/null
MONUMENTUM apply "$CS" > /dev/null
MONUMENTUM promote "$CS" --actor human/minhal > /dev/null

# a second, policy-violating-for-B change: docs/** is allowed in A only
mkdir -p docs
printf '# Setup\n\nOld setup notes.\n' > docs/setup.md
# refresh baseline is not needed: docs/setup.md was created after init, applies via loop
cat > docs.patch <<'EOF'
--- a/docs/setup.md
+++ b/docs/setup.md
@@ -1,3 +1,3 @@
 # Setup

-Old setup notes.
+Use pnpm install (see AGENTS.md).
EOF
cat > transcript2.json <<'EOF'
{
  "check_cmd": "node install.js pnpm",
  "runs": [ { "phase": "before", "exit_code": 1 }, { "phase": "after", "exit_code": 0 } ]
}
EOF
CS2=cs-20260831-uc3b
MONUMENTUM propose --layer context --target docs/setup.md --patch docs.patch \
  --rationale "propagate the pnpm note into docs" --producer producer-a --id "$CS2" > /dev/null
MONUMENTUM evidence "$CS2" --record ev.json --artifact transcript2.json > /dev/null 2>&1 || true
MONUMENTUM gate "$CS2" > /dev/null
MONUMENTUM apply "$CS2" > /dev/null
MONUMENTUM promote "$CS2" --actor human/minhal > /dev/null

MONUMENTUM sync > "$ART/sync-a.txt"
grep -q "pushed  $CS" "$ART/sync-a.txt"
grep -q "pushed  $CS2" "$ART/sync-a.txt"

# --- workspace B -----------------------------------------------------------------
B="$WORK/b"; mkdir -p "$B"
cp "$REPO_ROOT/scenarios/uc1/fixture/AGENTS.md" "$B/AGENTS.md"
cp "$REPO_ROOT/scenarios/uc1/fixture/install.js" "$B/install.js"
cd "$B"
MONUMENTUM init > /dev/null           # DEFAULT policy: docs/** NOT allowed
MONUMENTUM keygen --name consumer-b > /dev/null
cat > .monumentum/registry.yaml <<EOF
spec: monumentum/v0.1
kind: git-remote
remote: { url: "$(cd "$REG" && pwd -W 2>/dev/null || pwd)", branch: main }
verify: { require_signatures: true, pubkeys_dir: pubkeys }
signing: { key_file: keys/consumer-b.key, signer: consumer-b }
EOF
mkdir -p .monumentum/pubkeys
cp "$A/.monumentum/keys/producer-a.pub" .monumentum/pubkeys/

set +e
MONUMENTUM sync > "$ART/sync-b.txt" 2>&1
SYNC_EXIT=$?
set -e
[ "$SYNC_EXIT" -eq 0 ] || { cat "$ART/sync-b.txt"; echo "sync-b failed"; exit 1; }
grep -q "pulled  $CS" "$ART/sync-b.txt"
grep -q "rejected $CS2" "$ART/sync-b.txt"   # I4: refused by B's local policy

# pulled but not yet applied: local gates decide
grep -q "npm install to set up" AGENTS.md

MONUMENTUM gate "$CS" > /dev/null
MONUMENTUM apply "$CS" > /dev/null
T1=$("$PY" -c "import time; print(time.time())")

# --- asserts -------------------------------------------------------------------
grep -q "pnpm install" AGENTS.md
[ ! -f docs/setup.md ] || { echo "policy-violating change reached B's files"; exit 1; }
MONUMENTUM verify .
cd "$A" && MONUMENTUM verify . && cd "$B"
MONUMENTUM log --json > "$ART/journal-b.jsonl"
"$PY" - "$ART/journal-b.jsonl" "$CS" "$CS2" <<'EOF'
import json, sys
entries = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
cs, cs2 = sys.argv[2], sys.argv[3]
by_cs = {}
for e in entries:
    by_cs.setdefault(e.get("cs"), []).append(e["event"])
assert by_cs[cs] == ["proposed", "gated", "applied"], by_cs[cs]
assert by_cs[cs2] == ["proposed", "rejected"], by_cs[cs2]
EOF
cp "$A/.monumentum/journal/"*.ndjson "$ART/journal-a.ndjson"

ELAPSED=$("$PY" -c "print(round($T1 - $T0, 3))")
mkdir -p "$REPO_ROOT/experiments/scenarios/logs"
"$PY" - "$RUN_ID" "$ELAPSED" <<'EOF'
import json, os, sys
rec = {"run_id": sys.argv[1], "experiment": "scenario-uc3",
       "fleet_propagation_seconds": float(sys.argv[2]),
       "policy_violation_refused": True, "ok": True}
path = os.path.join(os.environ["REPO_ROOT"], "experiments", "scenarios", "logs",
                    sys.argv[1] + ".jsonl")
open(path, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
EOF
echo "UC3 ok (run $RUN_ID, propagation ${ELAPSED}s)"
