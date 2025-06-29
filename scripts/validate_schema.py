"""
validate_schema.py

Script to validate the structure and integrity of the DV standardization schema.
Checks for:
- Duplicated aliases
- Empty standard names or alias lists
- Non-string types in schema

Intended for use as a pre-commit check or development utility.
"""

import yaml
import sys
from collections import Counter

def load_schema(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def validate(schema):
    errors = []

    if not isinstance(schema, dict):
        errors.append("Schema root must be a dictionary of {standard_name: [aliases]}.")

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

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_schema.py path/to/schema.yaml")
        sys.exit(1)

    schema_path = sys.argv[1]
    try:
        schema = load_schema(schema_path)
        issues = validate(schema)
        if issues:
            print("Schema validation failed with the following issues:")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("Schema is valid ✅")
    except Exception as e:
        print(f"Error loading schema: {e}")
        sys.exit(1)
