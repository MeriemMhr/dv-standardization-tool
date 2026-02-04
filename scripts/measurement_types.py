"""
Measurement type definitions for DV standardization.

This module provides data structures for representing measurement categories,
scale types, and metadata about dependent variables in HCI research.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class MeasurementCategory(Enum):
    """Broad measurement category taxonomy for HCI DVs."""
    TIME = "Time"
    ACCURACY = "Accuracy"
    COUNT = "Count"
    LIKERT = "Likert"
    PROPORTION = "Proportion"
    BINARY = "Binary"
    CONTINUOUS = "Continuous"
    PHYSIOLOGICAL = "Physiological"


class ScaleType(Enum):
    """Stevens' scale typology for measurement levels."""
    NOMINAL = "nominal"      # Categories, no order
    ORDINAL = "ordinal"      # Ordered categories (e.g., Likert)
    INTERVAL = "interval"    # Equal intervals, no true zero
    RATIO = "ratio"          # Equal intervals, true zero


class Direction(Enum):
    """Interpretation direction for the measure."""
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"


@dataclass
class MeasurementMeta:
    """Metadata about a DV's measurement properties."""
    category: MeasurementCategory
    primary_unit: str
    allowed_units: List[str]
    scale_type: ScaleType
    direction: Direction
    confidence: float = 1.0
    inferred: bool = False
    matched_rules: List[str] = field(default_factory=list)
    needs_review: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category.value,
            "primary_unit": self.primary_unit,
            "allowed_units": self.allowed_units,
            "scale_type": self.scale_type.value,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "inferred": self.inferred,
            "matched_rules": self.matched_rules,
            "needs_review": self.needs_review
        }


# Mapping from category to default scale type
CATEGORY_SCALE_TYPES = {
    MeasurementCategory.TIME: ScaleType.RATIO,
    MeasurementCategory.ACCURACY: ScaleType.RATIO,
    MeasurementCategory.COUNT: ScaleType.RATIO,
    MeasurementCategory.LIKERT: ScaleType.ORDINAL,
    MeasurementCategory.PROPORTION: ScaleType.RATIO,
    MeasurementCategory.BINARY: ScaleType.NOMINAL,
    MeasurementCategory.CONTINUOUS: ScaleType.RATIO,
    MeasurementCategory.PHYSIOLOGICAL: ScaleType.RATIO,
}
