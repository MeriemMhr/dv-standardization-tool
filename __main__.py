"""
OpenDV-HCI CLI dispatcher.

Enables ``python -m opendv_hci`` usage with subcommands that delegate to the
existing entry-point modules.

Subcommands
-----------
standardize  Single-study DV standardization (scripts.convert_dv)
batch        Batch standardization across multiple studies (scripts.run_batch_standardization)
analyze      Multi-study meta-analysis (analyses.multi_study_analysis)
validate     Schema validation (scripts.validate_schema)
"""

from __future__ import annotations

import argparse
import sys

__version__ = "3.0.0"

EXAMPLES = """\
examples:
  python -m opendv_hci standardize --help
  python -m opendv_hci batch sources_manifest.yaml
  python -m opendv_hci analyze --output-dir results/
  python -m opendv_hci validate schemas/standard_dv_mapping.yaml
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m opendv_hci",
        description="OpenDV-HCI: schema-driven standardization and meta-analysis of dependent variables in HCI research.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", title="commands")

    subparsers.add_parser(
        "standardize",
        help="Run single-study DV standardization",
    )
    subparsers.add_parser(
        "batch",
        help="Run batch standardization across multiple studies",
    )
    subparsers.add_parser(
        "analyze",
        help="Run multi-study meta-analysis",
    )
    subparsers.add_parser(
        "validate",
        help="Validate a DV standardization schema",
    )

    return parser


def _run_standardize(argv: list[str]) -> None:
    try:
        from scripts.convert_dv import main
    except ImportError as exc:
        print(
            f"Error: could not import scripts.convert_dv ({exc}).\n"
            "Make sure the package is installed: pip install -e .",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.argv = ["opendv-standardize", *argv]
    main()


def _run_batch(argv: list[str]) -> None:
    try:
        from scripts.run_batch_standardization import main
    except ImportError as exc:
        print(
            f"Error: could not import scripts.run_batch_standardization ({exc}).\n"
            "Make sure the package is installed: pip install -e .",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.argv = ["opendv-batch", *argv]
    main()


def _run_analyze(argv: list[str]) -> None:
    try:
        from analyses.multi_study_analysis import main
    except ImportError as exc:
        print(
            f"Error: could not import analyses.multi_study_analysis ({exc}).\n"
            "Make sure the package is installed: pip install -e .",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.argv = ["opendv-analyze", *argv]
    main()


def _run_validate(argv: list[str]) -> None:
    try:
        from scripts.validate_schema import load_schema, validate
    except ImportError as exc:
        print(
            f"Error: could not import scripts.validate_schema ({exc}).\n"
            "Make sure the package is installed: pip install -e .",
            file=sys.stderr,
        )
        sys.exit(1)

    if not argv:
        print("Usage: python -m opendv_hci validate <path/to/schema.yaml>", file=sys.stderr)
        sys.exit(1)

    schema_path = argv[0]
    print("=" * 60)
    print("OpenDV-HCI Schema Validator")
    print("=" * 60)
    print(f"Validating: {schema_path}\n")

    try:
        schema = load_schema(schema_path)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {schema_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] Could not load schema: {exc}", file=sys.stderr)
        sys.exit(1)

    issues = validate(schema)
    if issues:
        print(f"[ERROR] Schema validation FAILED with {len(issues)} issue(s):\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        sys.exit(1)

    print("[OK] Schema is valid!\n")


_DISPATCH = {
    "standardize": _run_standardize,
    "batch": _run_batch,
    "analyze": _run_analyze,
    "validate": _run_validate,
}


def main() -> None:
    parser = _build_parser()

    # Parse only the first argument to identify the subcommand;
    # remaining argv is forwarded to the delegate so each module
    # can use its own argparse independently.
    args, remaining = parser.parse_known_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    _DISPATCH[args.command](remaining)


if __name__ == "__main__":
    main()
