"""
schema_utils.py

Utility functions to support schema loading, flattening, and updating
for the DV Standardization Tool.
"""

import yaml

def load_schema(path):
    """Load DV schema from YAML file."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def flatten_aliases(schema):
    """Return a set of all known aliases from a DV schema."""
    return {alias for aliases in schema.values() for alias in aliases}

def update_schema_with_suggestions(existing_schema, suggestions):
    """
    Merge new suggestions into an existing schema.

    Args:
        existing_schema (dict): Current schema loaded from YAML.
        suggestions (dict): New suggestions as {standard_name: [aliases]}.

    Returns:
        dict: Updated schema.
    """
    updated = existing_schema.copy()
    for std_name, aliases in suggestions.items():
        if std_name in updated:
            updated[std_name].extend(a for a in aliases if a not in updated[std_name])
        else:
            updated[std_name] = aliases
    return updated

def save_schema(schema, output_path):
    """Export schema to YAML format."""
    with open(output_path, 'w') as f:
        yaml.dump(schema, f, sort_keys=False)
