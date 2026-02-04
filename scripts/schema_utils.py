"""
schema_utils.py

Utility functions to support schema loading, flattening, and updating
for the DV Standardization Tool. Supports both legacy and new schema formats.
"""

import yaml
from typing import Dict, List, Optional, Set


def load_schema(path: str) -> Dict:
    """
    Load DV schema from YAML file.

    Supports both legacy format (flat dict) and new format (dvs list).

    Args:
        path: Path to YAML schema file

    Returns:
        Loaded schema dictionary
    """
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def load_measurement_categories(path: Optional[str] = None) -> Dict:
    """
    Load measurement categories schema.

    Args:
        path: Path to measurement_categories.yaml (defaults to schemas/measurement_categories.yaml)

    Returns:
        Loaded measurement categories dictionary
    """
    if path is None:
        from pathlib import Path
        current_dir = Path(__file__).parent
        path = current_dir.parent / "schemas" / "measurement_categories.yaml"

    with open(path, 'r') as f:
        return yaml.safe_load(f)


def flatten_aliases(schema: Dict) -> Set[str]:
    """
    Return a set of all known aliases from a DV schema.

    Supports both legacy and new schema formats.

    Args:
        schema: DV schema dictionary

    Returns:
        Set of all alias strings
    """
    aliases = set()

    # New format with 'dvs' list
    if 'dvs' in schema:
        for dv in schema['dvs']:
            dv_aliases = dv.get('aliases', [])
            aliases.update(dv_aliases)
            # Also add the id itself
            if 'id' in dv:
                aliases.add(dv['id'])
    else:
        # Legacy format: flat dict {standard_name: [aliases]}
        for aliases_list in schema.values():
            if isinstance(aliases_list, list):
                aliases.update(aliases_list)

    return aliases


def get_dv_by_id(schema: Dict, dv_id: str) -> Optional[Dict]:
    """
    Get a specific DV entry by its ID from the schema.

    Args:
        schema: DV schema dictionary
        dv_id: The DV ID to look up

    Returns:
        DV dictionary or None if not found
    """
    if 'dvs' in schema:
        for dv in schema['dvs']:
            if dv.get('id') == dv_id:
                return dv
    return None


def update_schema_with_suggestions(existing_schema: Dict, suggestions: Dict) -> Dict:
    """
    Merge new suggestions into an existing schema.

    Args:
        existing_schema: Current schema loaded from YAML
        suggestions: New suggestions as {standard_name: [aliases]}

    Returns:
        Updated schema dictionary
    """
    updated = existing_schema.copy()

    # Handle new schema format
    if 'dvs' in existing_schema:
        # Create a mapping of ids for quick lookup
        dv_map = {dv['id']: dv for dv in updated['dvs']}

        for std_name, new_aliases in suggestions.items():
            if std_name in dv_map:
                # Extend existing aliases
                existing_aliases = dv_map[std_name].get('aliases', [])
                for alias in new_aliases:
                    if alias not in existing_aliases:
                        existing_aliases.append(alias)
                dv_map[std_name]['aliases'] = existing_aliases
            else:
                # Add new DV entry
                updated['dvs'].append({
                    'id': std_name,
                    'label': std_name.replace('_', ' ').title(),
                    'cluster': 'uncategorized',
                    'aliases': new_aliases,
                    'instruments': [],
                    'units': [],
                    'notes': 'Community-contributed entry'
                })
    else:
        # Legacy format
        for std_name, aliases in suggestions.items():
            if std_name in updated:
                updated[std_name].extend(a for a in aliases if a not in updated[std_name])
            else:
                updated[std_name] = aliases

    return updated


def save_schema(schema: Dict, output_path: str) -> None:
    """
    Export schema to YAML format.

    Args:
        schema: Schema dictionary to save
        output_path: Path to save the YAML file
    """
    with open(output_path, 'w') as f:
        yaml.dump(schema, f, sort_keys=False, allow_unicode=True)


def build_alias_mapping(schema: Dict) -> Dict[str, str]:
    """
    Build a flat alias -> standard_name mapping from schema.

    Args:
        schema: DV schema dictionary

    Returns:
        Dictionary mapping aliases to standard DV IDs
    """
    mapping = {}

    if 'dvs' in schema:
        for dv in schema['dvs']:
            standard_name = dv.get('id')
            if not standard_name:
                continue

            # Map the id itself
            mapping[standard_name] = standard_name

            # Map all aliases
            for alias in dv.get('aliases', []):
                mapping[alias] = standard_name
    else:
        # Legacy format
        for standard, aliases in schema.items():
            if isinstance(aliases, list):
                mapping[standard] = standard
                for alias in aliases:
                    mapping[alias] = standard

    return mapping


def get_measurement_metadata(schema: Dict, dv_id: str) -> Optional[Dict]:
    """
    Extract measurement metadata for a specific DV.

    Args:
        schema: DV schema dictionary
        dv_id: The DV ID to look up

    Returns:
        Measurement metadata dictionary or None
    """
    dv = get_dv_by_id(schema, dv_id)
    if dv:
        return dv.get('measurement')
    return None


def validate_measurement_metadata(measurement: Dict) -> List[str]:
    """
    Validate measurement metadata structure.

    Args:
        measurement: Measurement metadata dictionary

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    required_fields = ['category', 'primary_unit', 'allowed_units', 'scale_type', 'direction']

    for field in required_fields:
        if field not in measurement:
            errors.append(f"Missing required field: {field}")

    # Validate category values
    valid_categories = ['Time', 'Accuracy', 'Count', 'Likert', 'Proportion', 'Binary', 'Continuous', 'Physiological']
    if 'category' in measurement and measurement['category'] not in valid_categories:
        errors.append(f"Invalid category: {measurement['category']}. Must be one of {valid_categories}")

    # Validate scale_type values
    valid_scale_types = ['nominal', 'ordinal', 'interval', 'ratio']
    if 'scale_type' in measurement and measurement['scale_type'] not in valid_scale_types:
        errors.append(f"Invalid scale_type: {measurement['scale_type']}. Must be one of {valid_scale_types}")

    # Validate direction values
    valid_directions = ['higher_is_better', 'lower_is_better', 'neutral']
    if 'direction' in measurement and measurement['direction'] not in valid_directions:
        errors.append(f"Invalid direction: {measurement['direction']}. Must be one of {valid_directions}")

    # Validate allowed_units is a list
    if 'allowed_units' in measurement and not isinstance(measurement['allowed_units'], list):
        errors.append("allowed_units must be a list")

    return errors
