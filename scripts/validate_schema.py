"""
validate_schema.py

Script to validate the structure and integrity of the DV standardization schema.

Checks for:
- Schema format (legacy vs. new format)
- Duplicated aliases
- Empty standard names or alias lists
- Non-string types in schema
- Measurement metadata completeness and validity (new format)
- Reserved keywords usage

Intended for use as a pre-commit check or development utility.
"""

import yaml
import sys
from collections import Counter
from schema_utils import validate_measurement_metadata


def load_schema(path: str) -> dict:
    """Load schema from YAML file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def validate_legacy_format(schema: dict) -> list:
    """
    Validate legacy schema format (flat dict of {standard_name: [aliases]}).

    Args:
        schema: Legacy schema dictionary

    Returns:
        List of error messages
    """
    errors = []
    alias_counter = Counter()

    for std_name, aliases in schema.items():
        if not std_name or not isinstance(std_name, str):
            errors.append(f"Invalid standard name: {std_name}")
        if not isinstance(aliases, list) or not aliases:
            errors.append(f"Invalid alias list for '{std_name}': must be a non-empty list.")
        for alias in aliases:
            if not alias or not isinstance(alias, str):
                errors.append(f"Invalid alias in '{std_name}': {alias}")
            alias_counter[alias] += 1

    # Check for duplicates
    duplicates = [alias for alias, count in alias_counter.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate aliases found: {duplicates}")

    return errors


def validate_new_format(schema: dict) -> list:
    """
    Validate new schema format (version 2.1+ with 'dvs' list).

    Args:
        schema: New schema dictionary with 'dvs' key

    Returns:
        List of error messages
    """
    errors = []
    alias_counter = Counter()
    id_set = set()

    # Reserved keywords that cannot be used as aliases
    reserved_keywords = ['null', 'none', 'nan', 'undefined', 'n/a']

    if 'dvs' not in schema:
        errors.append("New format schema must have 'dvs' key")
        return errors

    for idx, dv in enumerate(schema['dvs']):
        dv_id = dv.get('id', f'<missing_id_at_index_{idx}>')

        # Validate required fields
        if 'id' not in dv:
            errors.append(f"DV at index {idx} missing required field: 'id'")
            continue

        if 'label' not in dv:
            errors.append(f"DV '{dv_id}' missing required field: 'label'")

        if 'cluster' not in dv:
            errors.append(f"DV '{dv_id}' missing required field: 'cluster'")

        if 'aliases' not in dv:
            errors.append(f"DV '{dv_id}' missing required field: 'aliases'")

        # Check for duplicate IDs
        if dv_id in id_set:
            errors.append(f"Duplicate DV ID found: '{dv_id}'")
        id_set.add(dv_id)

        # Validate aliases
        aliases = dv.get('aliases', [])
        if not isinstance(aliases, list):
            errors.append(f"DV '{dv_id}': aliases must be a list")
        elif not aliases:
            errors.append(f"DV '{dv_id}': aliases list is empty")
        else:
            for alias in aliases:
                if not isinstance(alias, str):
                    errors.append(f"DV '{dv_id}': invalid alias type: {type(alias)}")
                elif not alias.strip():
                    errors.append(f"DV '{dv_id}': empty alias found")
                elif alias.lower() in reserved_keywords:
                    errors.append(f"DV '{dv_id}': alias '{alias}' is a reserved keyword")
                else:
                    alias_counter[alias] += 1

        # Validate measurement metadata (if present)
        if 'measurement' in dv:
            measurement = dv['measurement']
            measurement_errors = validate_measurement_metadata(measurement)
            for error in measurement_errors:
                errors.append(f"DV '{dv_id}' measurement metadata: {error}")

    # Check for duplicate aliases across DVs
    duplicates = [alias for alias, count in alias_counter.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate aliases found across DVs: {duplicates}")

    return errors


def validate(schema: dict) -> list:
    """
    Validate schema (auto-detects format).

    Args:
        schema: Schema dictionary

    Returns:
        List of error messages
    """
    if not isinstance(schema, dict):
        return ["Schema root must be a dictionary"]

    # Detect format
    if 'dvs' in schema:
        # New format
        return validate_new_format(schema)
    else:
        # Legacy format
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

        # Detect schema version
        version = schema.get('version', 'legacy')
        format_type = "New format (v2.1+)" if 'dvs' in schema else "Legacy format"
        print(f"Schema version: {version}")
        print(f"Format: {format_type}")
        print()

        issues = validate(schema)

        if issues:
            print(f"❌ Schema validation FAILED with {len(issues)} issue(s):")
            print()
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print()
            sys.exit(1)
        else:
            # Summary stats
            if 'dvs' in schema:
                num_dvs = len(schema['dvs'])
                total_aliases = sum(len(dv.get('aliases', [])) for dv in schema['dvs'])
                with_measurement = sum(1 for dv in schema['dvs'] if 'measurement' in dv)
                print(f"✓ Schema is valid!")
                print()
                print(f"Summary:")
                print(f"  - Total DVs: {num_dvs}")
                print(f"  - Total aliases: {total_aliases}")
                print(f"  - DVs with measurement metadata: {with_measurement}/{num_dvs}")
            else:
                print(f"✓ Schema is valid!")

            print()
            sys.exit(0)

    except yaml.YAMLError as e:
        print(f"❌ YAML parsing error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ File not found: {schema_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
