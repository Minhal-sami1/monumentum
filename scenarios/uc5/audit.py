#!/usr/bin/env python
"""UC5 audit reconstruction: answer "why does this workspace behave the way
it behaves today?" from the journal ALONE.

Sources: .monumentum/journal/*.ndjson - nothing else. No git log, no source
diffs, no monumentum import (the auditor is independent of the executor).
The reconstruction is then CHECKED against reality: current file hashes
must match the journal's recorded target states, and the replayed
effective levels must match .monumentum/state.json (reality cross-check only).

Exit 0: journal intact, reconstruction printed, reality matches.
Exit 1: any mismatch, named.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def canonical(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def combined_hash(root: Path, targets: list[str]) -> str:
    pairs = sorted((t, sha256_file(root / t)) for t in targets)
    return sha256_bytes(canonical([list(p) for p in pairs]).encode("utf-8"))


def read_journal(journal_dir: Path) -> list[dict]:
    lines: list[bytes] = []
    for file in sorted(journal_dir.glob("*.ndjson")):
        for raw in file.read_bytes().split(b"\n"):
            if raw.strip():
                lines.append(raw)
    # independent chain verification (invariant I2)
    prev: bytes | None = None
    entries = []
    for i, line in enumerate(lines):
        entry = json.loads(line.decode("utf-8"))
        if entry["seq"] != i:
            sys.exit(f"AUDIT FAIL: sequence break at {i}")
        expected_prev = sha256_bytes(prev) if prev is not None else None
        if entry["prev"] != expected_prev:
            sys.exit(f"AUDIT FAIL: hash chain broken at seq {i}")
        prev = line
        entries.append(entry)
    if not entries or entries[0]["event"] != "genesis":
        sys.exit("AUDIT FAIL: no genesis entry")
    return entries


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    entries = read_journal(root / ".monumentum" / "journal")

    changesets: dict[str, dict] = {}
    levels: dict[str, str] = dict(entries[0].get("ext", {}).get("effective_levels", {}))
    level_history: list[str] = []

    for entry in entries:
        cs_id = entry.get("cs")
        if cs_id:
            cs = changesets.setdefault(cs_id, {"events": []})
            cs["events"].append(entry["event"])
            if entry["event"] == "proposed":
                cs["rationale"] = entry.get("note", "(no rationale recorded)")
                cs["actor"] = entry["actor"]
                cs["layer"] = entry.get("ext", {}).get("layer")
                cs["targets"] = entry.get("ext", {}).get("targets", [])
            elif entry["event"] in ("applied", "rolled_back"):
                cs[entry["event"]] = {
                    "actor": entry["actor"],
                    "gate": entry.get("decision", {}).get("gate"),
                    "after": entry.get("target_state", {}).get("after"),
                }
            elif entry["event"] in ("rejected", "approved"):
                cs.setdefault(entry["event"], {})
                cs[entry["event"]]["actor"] = entry["actor"]
                reason = entry.get("decision", {}).get("reason")
                if reason:
                    cs[entry["event"]]["reason"] = reason
        if entry["event"] == "policy_changed":
            eff = entry.get("ext", {}).get("policy_effective")
            if eff:
                levels[eff["layer"]] = eff["to"]
                level_history.append(
                    f"{eff['layer']}: {eff['from']} -> {eff['to']} "
                    f"({entry.get('decision', {}).get('reason', '')})"
                )

    surviving = {k: v for k, v in changesets.items()
                 if "applied" in v and "rolled_back" not in v}
    rolled = {k: v for k, v in changesets.items() if "rolled_back" in v}
    rejected = {k: v for k, v in changesets.items()
                if "rejected" in v and "applied" not in v}

    print(f"# Audit reconstruction: {root}")
    print(f"# Source: journal only ({len(entries)} entries, chain verified)\n")
    print("## Why this workspace behaves the way it does today\n")
    print("### Changes in effect (applied, never rolled back)")
    for cs_id, cs in sorted(surviving.items()):
        applied = cs["applied"]
        print(f"- {cs_id} [{cs.get('layer')}] targets={cs.get('targets')}")
        print(f"    why:   {cs.get('rationale')}")
        print(f"    who:   proposed by {cs.get('actor')}; "
              f"applied via {applied['gate']} by {applied['actor']}")
        if "approved" in cs:
            print(f"    review: approved by {cs['approved']['actor']}")
    print("\n### Changes tried and reverted")
    for cs_id, cs in sorted(rolled.items()):
        print(f"- {cs_id} [{cs.get('layer')}]: {cs.get('rationale')}")
        print(f"    rolled back by {cs['rolled_back']['actor']}")
    print("\n### Changes refused")
    for cs_id, cs in sorted(rejected.items()):
        reason = cs.get("rejected", {}).get("reason", "")
        print(f"- {cs_id}: {reason} (by {cs.get('rejected', {}).get('actor')})")
    print("\n### Current autonomy levels (replayed from genesis + policy_changed)")
    for layer, level in sorted(levels.items()):
        print(f"- {layer}: {level}")
    for line in level_history:
        print(f"    ratchet: {line}")

    # ---- reality check -----------------------------------------------------
    # Only the LAST change touching a target is checkable against the current
    # tree; earlier states were legitimately overwritten by later changes.
    problems = []
    final_owner: dict[str, str] = {}
    for entry in entries:
        if entry["event"] in ("applied", "rolled_back") and entry.get("cs"):
            for target in changesets[entry["cs"]].get("targets", []):
                final_owner[target] = entry["cs"]
    for cs_id, cs in sorted({**surviving, **rolled}.items()):
        targets = cs.get("targets", [])
        if not targets or any(final_owner.get(t) != cs_id for t in targets):
            continue  # superseded by a later change; not checkable
        kind = "rolled_back" if cs_id in rolled else "applied"
        expected = cs[kind]["after"]
        actual = combined_hash(root, targets)
        if actual != expected:
            problems.append(
                f"{cs_id}: current files do not match journal {kind} target_state.after"
            )
    state_path = root / ".monumentum" / "state.json"
    if state_path.is_file():
        state_levels = json.loads(state_path.read_text(encoding="utf-8")).get(
            "effective_levels", {}
        )
        if state_levels != levels:
            problems.append(
                f"replayed levels {levels} do not match executor state {state_levels}"
            )

    print("\n## Reality check")
    if problems:
        for problem in problems:
            print(f"MISMATCH: {problem}")
        return 1
    print("journal-derived state matches the working tree and executor state. AUDIT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
