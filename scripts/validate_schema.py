"""
validate_schema.py

Script to validate the structure and integrity of the DV standardization schema.

Checks for:
- Schema format (legacy vs. new format)
- Ambiguous aliases across canonical IDs
- Empty standard names or alias lists
- Non-string types in schema
- Measurement metadata completeness and validity (new format)
- Reserved keywords usage

Intended for use as a pre-commit check or development utility.
"""

from __future__ import annotations

import sys
from collections import defaultdict

import yaml

try:
    from scripts.schema_utils import validate_measurement_metadata
except ImportError:
    from schema_utils import validate_measurement_metadata


def load_schema(path: str) -> dict:
    """Load schema from YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _normalize_alias(alias: str) -> str:
    return alias.strip().lower()


def validate_legacy_format(schema: dict) -> list[str]:
    """
    Validate legacy schema format (flat dict of {standard_name: [aliases]}).

    Args:
        schema: Legacy schema dictionary

    Returns:
        List of error messages
    """
    errors: list[str] = []
    alias_to_standards: dict[str, set[str]] = defaultdict(set)

    for std_name, aliases in schema.items():
        if not std_name or not isinstance(std_name, str):
            errors.append(f"Invalid standard name: {std_name}")
        if not isinstance(aliases, list) or not aliases:
            errors.append(f"Invalid alias list for '{std_name}': must be a non-empty list.")
            continue
        for alias in aliases:
            if not alias or not isinstance(alias, str):
                errors.append(f"Invalid alias in '{std_name}': {alias}")
                continue
            alias_to_standards[_normalize_alias(alias)].add(str(std_name))

    ambiguous_aliases = {
        alias: sorted(standards)
        for alias, standards in alias_to_standards.items()
        if len(standards) > 1
    }
    if ambiguous_aliases:
        preview = ", ".join(
            f"{alias} -> {standards}"
            for alias, standards in sorted(ambiguous_aliases.items())[:10]
        )
        errors.append(f"Ambiguous aliases found across standards: {preview}")

    return errors


def validate_new_format(schema: dict) -> list[str]:
    """
    Validate new schema format (version 2.1+ with 'dvs' list).

    Args:
        schema: New schema dictionary with 'dvs' key

    Returns:
        List of error messages
    """
    errors: list[str] = []
    alias_to_ids: dict[str, set[str]] = defaultdict(set)
    id_set: set[str] = set()
    schema_type = str(schema.get("schema_type", "dv")).strip().lower()
    requires_dv_fields = schema_type in {"", "dv", "dependent_variable", "dependent_variables"}

    reserved_keywords = ["null", "none", "nan", "undefined", "n/a"]

    if "dvs" not in schema:
        errors.append("New format schema must have 'dvs' key")
        return errors

    for idx, dv in enumerate(schema["dvs"]):
        if not isinstance(dv, dict):
            errors.append(f"DV at index {idx} must be a mapping.")
            continue

        dv_id = str(dv.get("id", f"<missing_id_at_index_{idx}>"))

        if "id" not in dv:
            errors.append(f"DV at index {idx} missing required field: 'id'")
            continue

        if requires_dv_fields:
            if "label" not in dv:
                errors.append(f"DV '{dv_id}' missing required field: 'label'")

            if "cluster" not in dv:
                errors.append(f"DV '{dv_id}' missing required field: 'cluster'")

        if "aliases" not in dv:
            errors.append(f"DV '{dv_id}' missing required field: 'aliases'")

        if dv_id in id_set:
            errors.append(f"Duplicate DV ID found: '{dv_id}'")
        id_set.add(dv_id)

        aliases = dv.get("aliases", [])
        if not isinstance(aliases, list):
            errors.append(f"DV '{dv_id}': aliases must be a list")
        elif not aliases:
            errors.append(f"DV '{dv_id}': aliases list is empty")
        else:
            for alias in aliases:
                if not isinstance(alias, str):
                    errors.append(f"DV '{dv_id}': invalid alias type: {type(alias)}")
                    continue
                if not alias.strip():
                    errors.append(f"DV '{dv_id}': empty alias found")
                    continue

                normalized_alias = _normalize_alias(alias)
                if normalized_alias in reserved_keywords:
                    errors.append(f"DV '{dv_id}': alias '{alias}' is a reserved keyword")
                    continue

                alias_to_ids[normalized_alias].add(dv_id)

        if requires_dv_fields and "measurement" in dv:
            measurement_errors = validate_measurement_metadata(dv["measurement"])
            for error in measurement_errors:
                errors.append(f"DV '{dv_id}' measurement metadata: {error}")

    ambiguous_aliases = {
        alias: sorted(ids)
        for alias, ids in alias_to_ids.items()
        if len(ids) > 1
    }
    if ambiguous_aliases:
        preview = ", ".join(
            f"{alias} -> {ids}"
            for alias, ids in sorted(ambiguous_aliases.items())[:10]
        )
        errors.append(f"Ambiguous aliases found across DVs: {preview}")

    return errors


def validate(schema: dict) -> list[str]:
    """
    Validate schema (auto-detects format).

    Args:
        schema: Schema dictionary

    Returns:
        List of error messages
    """
    if not isinstance(schema, dict):
        return ["Schema root must be a dictionary"]

    if "dvs" in schema:
        return validate_new_format(schema)
    return validate_legacy_format(schema)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_schema.py path/to/schema.yaml")
        print("\nExample:")
        print("  python validate_schema.py schemas/standard_dv_mapping.yaml")
        sys.exit(1)

    schema_path = sys.argv[1]

    print("=" * 60)
    print("OpenDV-HCI Schema Validator")
    print("=" * 60)
    print(f"Validating: {schema_path}")
    print()

    try:
        schema = load_schema(schema_path)

        version = schema.get("version", "legacy") if isinstance(schema, dict) else "unknown"
        if isinstance(schema, dict) and "dvs" in schema:
            schema_type = str(schema.get("schema_type", "dv")).strip().lower()
            format_type = (
                f"New format ({schema_type})" if schema_type else "New format (dv)"
            )
        else:
            format_type = "Legacy format"
        print(f"Schema version: {version}")
        print(f"Format: {format_type}")
        print()

        issues = validate(schema)

        if issues:
            print(f"[ERROR] Schema validation FAILED with {len(issues)} issue(s):")
            print()
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print()
            sys.exit(1)

        if isinstance(schema, dict) and "dvs" in schema:
            num_dvs = len(schema["dvs"])
            total_aliases = sum(len(dv.get("aliases", [])) for dv in schema["dvs"] if isinstance(dv, dict))
            with_measurement = sum(1 for dv in schema["dvs"] if isinstance(dv, dict) and "measurement" in dv)
            print("[OK] Schema is valid!")
            print()
            print("Summary:")
            print(f"  - Total DVs: {num_dvs}")
            print(f"  - Total aliases: {total_aliases}")
            print(f"  - DVs with measurement metadata: {with_measurement}/{num_dvs}")
        else:
            print("[OK] Schema is valid!")

        print()
        sys.exit(0)

    except yaml.YAMLError as exc:
        print(f"[ERROR] YAML parsing error: {exc}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {schema_path}")
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] Unexpected error: {exc}")
        sys.exit(1)
