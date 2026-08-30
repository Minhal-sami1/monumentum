# Shared helpers for adversarial tests. Source this from each t*.sh.
AGENTLOOP() { "$PY" -m agentloop.cli "$@"; }

# Fresh governed workspace in a scratch dir. Sets $WS (cwd) and $ART.
setup_ws() {
  local name="$1"
  local dir
  dir="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)/out/$name"
  rm -rf "$dir"; mkdir -p "$dir"
  ART="$dir/artifacts"; mkdir -p "$ART"
  WS="$dir/work"; mkdir -p "$WS"
  printf '# Agent notes\n\nUse npm install to set up.\n' > "$WS/AGENTS.md"
  mkdir -p "$WS/tools"
  printf "def helper():\n    return 1\n" > "$WS/tools/util.py"
  cd "$WS"
  AGENTLOOP init > /dev/null
}

# Assert a command fails (non-zero). Usage: must_fail <msg> -- cmd args...
must_fail() {
  local msg="$1"; shift; [ "$1" = "--" ] && shift
  set +e; "$@" > /dev/null 2>&1; local rc=$?; set -e
  [ "$rc" -ne 0 ] || { echo "SECURITY FAIL: $msg (command unexpectedly succeeded)"; exit 1; }
}

# Assert a file does NOT contain a string.
assert_absent() { # file needle
  ! grep -q "$2" "$1" || { echo "SECURITY FAIL: '$2' present in $1"; exit 1; }
}

log_result() { # test-id detail
  mkdir -p "$REPO_ROOT/experiments/adversarial/logs"
  "$PY" - "$1" "$2" <<'EOF'
import json, os, sys
rec = {"run_id": sys.argv[1] + "-" + __import__("datetime").datetime.now(
    __import__("datetime").UTC).strftime("%Y%m%d-%H%M%S"),
    "experiment": "adversarial", "test": sys.argv[1], "outcome": sys.argv[2], "ok": True}
path = os.path.join(os.environ["REPO_ROOT"], "experiments", "adversarial", "logs",
                    rec["run_id"] + ".jsonl")
open(path, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
EOF
}
