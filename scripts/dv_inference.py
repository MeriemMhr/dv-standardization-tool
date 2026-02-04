"""
DV Measurement Type Inference Module

This module provides heuristic-based inference of measurement categories,
units, and scale types from DV labels. It uses pattern matching, keyword
detection, and instrument recognition to automatically classify DVs.
"""

import re
import yaml
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from measurement_types import (
    MeasurementMeta,
    MeasurementCategory,
    ScaleType,
    Direction,
    CATEGORY_SCALE_TYPES
)


def load_inference_rules(
    rules_path: Optional[str] = None
) -> Dict:
    """
    Load inference rules from external YAML file.

    Args:
        rules_path: Path to inference_rules.yaml (defaults to schemas/inference_rules.yaml)

    Returns:
        Dictionary containing category_rules, unit_rules, and instrument_scales
    """
    if rules_path is None:
        # Default to schemas/inference_rules.yaml relative to this file
        current_dir = Path(__file__).parent
        rules_path = current_dir.parent / "schemas" / "inference_rules.yaml"

    with open(rules_path, 'r') as f:
        rules = yaml.safe_load(f)

    return rules


def match_unit_marker(unit_marker: str, unit_rules: Dict) -> Optional[Tuple[str, str]]:
    """
    Match a unit marker (e.g., from parentheses) to a known unit.

    Args:
        unit_marker: The text found in parentheses (e.g., "s", "ms", "%")
        unit_rules: Dictionary of unit rules from inference_rules.yaml

    Returns:
        Tuple of (unit_name, category) or None if no match
    """
    unit_marker_lower = unit_marker.lower().strip()

    for unit_name, unit_info in unit_rules.items():
        for pattern in unit_info.get('patterns', []):
            if re.search(pattern, unit_marker_lower, re.IGNORECASE):
                return (unit_name, unit_info['category'])

    return None


def infer_measurement_type(
    dv_label: str,
    context: Optional[Dict] = None,
    rules: Optional[Dict] = None
) -> MeasurementMeta:
    """
    Infer measurement category and unit from a DV label.

    Priority order:
    1. Instrument name matching (highest confidence)
    2. Unit markers in parentheses
    3. Keyword/suffix/pattern matching

    Args:
        dv_label: Raw DV name (e.g., "Task Completion Time (s)")
        context: Optional context (instrument name, domain hints)
        rules: Pre-loaded rules (for batch processing efficiency)

    Returns:
        MeasurementMeta with inferred properties and confidence score
    """
    # Load rules if not provided
    if rules is None:
        rules = load_inference_rules()

    category_rules = rules.get('category_rules', {})
    unit_rules = rules.get('unit_rules', {})
    instrument_scales = rules.get('instrument_scales', {})

    label_lower = dv_label.lower().strip()
    matches = {"category": [], "unit": [], "rules": []}

    # Priority 1: Check for instrument names (highest confidence)
    for instrument, meta in instrument_scales.items():
        instrument_lower = instrument.lower()
        # Check instrument name and aliases
        aliases = meta.get('aliases', [])
        all_names = [instrument_lower] + [a.lower() for a in aliases]

        for name in all_names:
            if name in label_lower:
                return MeasurementMeta(
                    category=MeasurementCategory[meta['category'].upper()],
                    primary_unit=meta['scale'],
                    allowed_units=[meta['scale']],
                    scale_type=ScaleType[meta['scale_type'].upper()],
                    direction=Direction[meta['direction'].upper()],
                    confidence=0.95,
                    inferred=True,
                    matched_rules=[f"instrument:{instrument}"],
                    needs_review=False
                )

    # Priority 2: Check unit markers in parentheses (e.g., "Time (s)")
    unit_in_parens = re.search(r"\(([^)]+)\)$", dv_label)
    if unit_in_parens:
        unit_marker = unit_in_parens.group(1)
        matched_unit = match_unit_marker(unit_marker, unit_rules)
        if matched_unit:
            unit_name, unit_category = matched_unit
            matches["unit"].append(unit_name)
            matches["category"].append((unit_category, 2.0))  # High score for unit match
            matches["rules"].append(f"unit_marker:({unit_marker})")

    # Priority 3: Apply keyword/suffix/pattern rules
    for category, rules_dict in category_rules.items():
        score = 0

        # Check keywords
        for keyword in rules_dict.get('keywords', []):
            if keyword in label_lower:
                score += 1
                matches["rules"].append(f"keyword:{keyword}")

        # Check suffixes (stronger indicator)
        for suffix in rules_dict.get('suffixes', []):
            if label_lower.endswith(suffix):
                score += 2
                matches["rules"].append(f"suffix:{suffix}")

        # Check regex patterns
        for pattern in rules_dict.get('patterns', []):
            if re.search(pattern, label_lower, re.IGNORECASE):
                score += 1.5
                matches["rules"].append(f"pattern:{pattern}")

        if score > 0:
            matches["category"].append((category, score))

    # Select highest-scoring category
    if matches["category"]:
        best_category = max(matches["category"], key=lambda x: x[1])
        category_name = best_category[0]
        category_score = best_category[1]
        confidence = min(0.9, 0.5 + category_score * 0.1)
    else:
        # Default fallback
        category_name = "Continuous"
        confidence = 0.3

    # Convert category name to enum
    try:
        category_enum = MeasurementCategory[category_name.upper()]
    except KeyError:
        category_enum = MeasurementCategory.CONTINUOUS

    # Determine scale type from category
    scale_type = CATEGORY_SCALE_TYPES.get(category_enum, ScaleType.RATIO)

    # Determine primary unit
    primary_unit = matches["unit"][0] if matches["unit"] else None

    # Determine direction (default neutral, can be overridden)
    direction = Direction.NEUTRAL

    # Create measurement metadata
    return MeasurementMeta(
        category=category_enum,
        primary_unit=primary_unit or "varies",
        allowed_units=[primary_unit] if primary_unit else [],
        scale_type=scale_type,
        direction=direction,
        confidence=confidence,
        inferred=True,
        matched_rules=matches["rules"],
        needs_review=confidence < 0.7
    )


def batch_infer(
    dv_labels: List[str],
    confidence_threshold: float = 0.7,
    rules: Optional[Dict] = None
) -> List[Tuple[str, MeasurementMeta, bool]]:
    """
    Batch inference with confidence filtering.

    Args:
        dv_labels: List of DV label strings
        confidence_threshold: Minimum confidence for auto-accept
        rules: Pre-loaded rules (loaded once for efficiency)

    Returns:
        List of (label, meta, needs_review) tuples
    """
    # Load rules once for batch processing
    if rules is None:
        rules = load_inference_rules()

    results = []
    for label in dv_labels:
        meta = infer_measurement_type(label, rules=rules)
        needs_review = meta.confidence < confidence_threshold
        results.append((label, meta, needs_review))

    return results


def validate_inference(
    dv_label: str,
    expected_category: str,
    expected_unit: str,
    rules: Optional[Dict] = None
) -> Tuple[bool, str]:
    """
    Validate inference against expected values (for testing).

    Args:
        dv_label: DV label to test
        expected_category: Expected category name
        expected_unit: Expected unit
        rules: Optional pre-loaded rules

    Returns:
        (is_correct, explanation) tuple
    """
    meta = infer_measurement_type(dv_label, rules=rules)

    category_correct = meta.category.value == expected_category
    unit_correct = meta.primary_unit == expected_unit or meta.primary_unit in [expected_unit, "varies"]

    if category_correct and unit_correct:
        return (True, f"✓ Correct inference: {meta.category.value}, {meta.primary_unit}")
    elif category_correct:
        return (False, f"✗ Category correct but unit mismatch: expected {expected_unit}, got {meta.primary_unit}")
    else:
        return (False, f"✗ Category mismatch: expected {expected_category}, got {meta.category.value}")


def get_measurement_from_schema(
    dv_id: str,
    schema_path: Optional[str] = None
) -> Optional[MeasurementMeta]:
    """
    Get measurement metadata from the standard schema (ground truth).

    Args:
        dv_id: The standardized DV ID
        schema_path: Path to standard_dv_mapping.yaml

    Returns:
        MeasurementMeta from schema or None if not found
    """
    if schema_path is None:
        current_dir = Path(__file__).parent
        schema_path = current_dir.parent / "schemas" / "standard_dv_mapping.yaml"

    with open(schema_path, 'r') as f:
        schema = yaml.safe_load(f)

    for dv in schema.get('dvs', []):
        if dv.get('id') == dv_id:
            measurement = dv.get('measurement', {})
            if measurement:
                return MeasurementMeta(
                    category=MeasurementCategory[measurement['category'].upper()],
                    primary_unit=measurement['primary_unit'],
                    allowed_units=measurement['allowed_units'],
                    scale_type=ScaleType[measurement['scale_type'].upper()],
                    direction=Direction[measurement['direction'].upper()],
                    confidence=1.0,
                    inferred=False,
                    matched_rules=["schema_defined"],
                    needs_review=False
                )

    return None
