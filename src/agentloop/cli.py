"""agentloop CLI: the reference Executor's command surface.

Exit codes: 0 success, 1 rejected or failed, 2 queued for review or usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentloop import __version__
from agentloop.changeset import (
    ChangeSetError,
    attach_evidence,
    create_changeset,
    ingest_changeset,
    load_changeset,
)
from agentloop.check import check_schemas
from agentloop.executor import (
    S_QUEUED,
    ExecutorError,
    Outcome,
    apply_changeset,
    approve,
    gate,
    init_workspace,
    propose,
    reject_changeset,
    rollback,
    verify,
)
from agentloop.policy import PolicyError
from agentloop.workspace import Workspace, WorkspaceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentloop",
        description="Reference Executor for the Loop standard (spec loop/v0.1).",
    )
    parser.add_argument("--version", action="version", version=f"agentloop {__version__}")
    parser.add_argument(
        "-C", "--workspace", type=Path, default=Path("."), help="workspace root (default: .)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-schemas", help="validate the conformance golden corpus")
    p.add_argument("--golden", type=Path, default=Path("conformance/golden"))

    sub.add_parser("init", help="scaffold .loop/ with default policy and a genesis journal entry")

    p = sub.add_parser("propose", help="create or ingest a ChangeSet, journal it, validate it")
    p.add_argument("--from-dir", type=Path, help="prepared ChangeSet folder to ingest")
    p.add_argument("--layer", choices=["context", "capability", "architecture"])
    p.add_argument("--target", action="append", default=[], help="repeatable target path")
    p.add_argument("--patch", type=Path, help="unified diff payload file")
    p.add_argument("--folder", type=Path, help="folder payload (mirrors target paths)")
    p.add_argument("--opaque-ref", help="external payload reference (weight updates)")
    p.add_argument("--rationale")
    p.add_argument("--producer", default="cli/human")
    p.add_argument("--model")
    p.add_argument("--session")
    p.add_argument("--trigger")
    p.add_argument("--id", dest="cs_id", help="explicit changeset id")

    p = sub.add_parser("evidence", help="attach an evidence record (+ artifact) to a ChangeSet")
    p.add_argument("cs_id")
    p.add_argument("--record", type=Path, required=True, help="evidence record JSON file")
    p.add_argument("--artifact", type=Path, help="artifact file; its hash fills the record")

    p = sub.add_parser("gate", help="evaluate policy gates for a validated ChangeSet")
    p.add_argument("cs_id")

    p = sub.add_parser("apply", help="apply a gate-approved or human-approved ChangeSet")
    p.add_argument("cs_id")

    p = sub.add_parser("approve", help="approve a queued ChangeSet (reviewer) and apply it")
    p.add_argument("cs_id")
    p.add_argument("--actor", required=True, help="reviewer/<id> or human/<id>")

    p = sub.add_parser("reject", help="reject a queued ChangeSet (reviewer)")
    p.add_argument("cs_id")
    p.add_argument("--actor", required=True)
    p.add_argument("--reason", default="rejected by reviewer")

    p = sub.add_parser("rollback", help="restore the exact pre-apply state of a ChangeSet")
    p.add_argument("cs_id")
    p.add_argument("--actor", default="human/operator")

    p = sub.add_parser("log", help="print journal entries")
    p.add_argument("--cs", help="filter by changeset id")
    p.add_argument("--json", action="store_true", help="one JSON entry per line")

    p = sub.add_parser("verify", help="verify journal chain and managed-file heads")
    p.add_argument("path", nargs="?", type=Path, help="workspace root (overrides -C)")

    p = sub.add_parser("status", help="print queue and changeset states")
    p.add_argument("--json", action="store_true")

    return parser


def _print_outcome(outcome: Outcome) -> int:
    if outcome.ok:
        print(f"{outcome.status}" + (f": {outcome.reason}" if outcome.reason else ""))
        return 2 if outcome.status == S_QUEUED else 0
    print(f"{outcome.status}: {outcome.reason}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except (ExecutorError, ChangeSetError, WorkspaceError, PolicyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    ws = Workspace(args.workspace)

    if args.command == "check-schemas":
        return check_schemas(args.golden)

    if args.command == "init":
        init_workspace(args.workspace)
        print(f"Initialized .loop/ in {ws.root}")
        print("Next steps:")
        print("  1. Review .loop/policy.yaml (context L2, capability L1, architecture L1).")
        print("  2. Propose a change:  agentloop propose --layer context --target AGENTS.md \\")
        print("       --patch fix.patch --rationale 'why'")
        print("  3. Attach evidence:   agentloop evidence <cs-id> --record ev.json --artifact log")
        print("  4. Gate and apply:    agentloop gate <cs-id> && agentloop apply <cs-id>")
        print("  5. Verify anytime:    agentloop verify .")
        return 0

    if args.command == "propose":
        ws.require()
        if args.from_dir:
            cs = ingest_changeset(args.from_dir, ws.changesets_dir)
        else:
            if not (args.layer and args.target and args.rationale):
                print("error: --layer, --target, and --rationale are required", file=sys.stderr)
                return 2
            cs = create_changeset(
                ws.changesets_dir,
                layer=args.layer,
                targets=args.target,
                rationale=args.rationale,
                producer=args.producer,
                patch_file=args.patch,
                folder_payload=args.folder,
                opaque_ref=args.opaque_ref,
                model=args.model,
                session=args.session,
                trigger=args.trigger,
                cs_id=args.cs_id,
            )
        outcome = propose(ws, cs)
        print(f"{cs.envelope.get('id')}: {outcome.status}"
              + (f" ({outcome.reason})" if outcome.reason else ""))
        return 0 if outcome.ok else 1

    if args.command == "evidence":
        ws.require()
        cs = load_changeset(ws.changesets_dir / args.cs_id)
        record = attach_evidence(cs, args.record, args.artifact)
        print(f"attached {record['id']} to {args.cs_id}")
        return 0

    if args.command == "gate":
        return _print_outcome(gate(ws, args.cs_id))

    if args.command == "apply":
        return _print_outcome(apply_changeset(ws, args.cs_id))

    if args.command == "approve":
        return _print_outcome(approve(ws, args.cs_id, args.actor))

    if args.command == "reject":
        return _print_outcome(reject_changeset(ws, args.cs_id, args.actor, args.reason))

    if args.command == "rollback":
        return _print_outcome(rollback(ws, args.cs_id, args.actor))

    if args.command == "log":
        ws.require()
        for entry in ws.journal.entries():
            if args.cs and entry.get("cs") != args.cs:
                continue
            if args.json:
                print(json.dumps(entry, sort_keys=True))
            else:
                cs_part = f" cs={entry['cs']}" if entry.get("cs") else ""
                reason = entry.get("decision", {}).get("reason")
                reason_part = f" reason={reason!r}" if reason else ""
                print(f"[{entry['seq']:>4}] {entry['ts']} {entry['event']:<14}"
                      f"{cs_part} actor={entry['actor']}{reason_part}")
        return 0

    if args.command == "verify":
        target = Workspace(args.path) if args.path else ws
        problems = verify(target)
        if problems:
            for problem in problems:
                print(f"FAIL {problem}", file=sys.stderr)
            return 1
        print(f"verify OK: journal chain intact, managed files match ({target.root})")
        return 0

    if args.command == "status":
        ws.require()
        state = ws.read_state()
        if args.json:
            print(json.dumps(state, indent=2, sort_keys=True))
            return 0
        levels = state.get("effective_levels", {})
        print("effective levels: " + ", ".join(f"{k}={v}" for k, v in sorted(levels.items())))
        queue = state.get("queue", [])
        print(f"queue ({len(queue)}): " + (", ".join(queue) if queue else "empty"))
        for cs_id, meta in sorted(state.get("changesets", {}).items()):
            print(f"  {cs_id}: {meta['status']} [{meta.get('layer')}] {meta.get('targets')}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
