"""agentloop CLI. m1 surface: check-schemas. m2 adds the executor verbs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentloop import __version__
from agentloop.check import check_schemas


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentloop",
        description="Reference Executor for the Loop standard (spec loop/v0.1).",
    )
    parser.add_argument("--version", action="version", version=f"agentloop {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser(
        "check-schemas",
        help="Validate the golden corpus: valid files must pass, invalid files must fail.",
    )
    p_check.add_argument(
        "--golden",
        type=Path,
        default=Path("conformance/golden"),
        help="Golden corpus directory (default: conformance/golden).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check-schemas":
        return check_schemas(args.golden)
    return 2


if __name__ == "__main__":
    sys.exit(main())
