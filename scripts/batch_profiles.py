"""Dataset-type and mapping-domain helpers for batch standardization."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml

logger = logging.getLogger(__name__)

DATASET_TYPE_RESULTS = "results_table"
DATASET_TYPE_QUESTIONNAIRE = "questionnaire"
DATASET_TYPE_SENSOR = "sensor_stream"
DATASET_TYPE_DETECTION = "object_detection"
DATASET_TYPE_PROCESS = "process_log"

MAPPING_DOMAIN_DV = "dv"
MAPPING_DOMAIN_SENSOR = "sensor"
MAPPING_DOMAIN_DETECTION = "detection"
MAPPING_DOMAIN_METADATA = "metadata"
MAPPING_DOMAIN_CUSTOM = "custom"
MAPPING_DOMAIN_UNMAPPED = "unmapped"
MAPPING_DOMAIN_BLOCKED = "blocked"

# Path to the YAML-driven profiles file (may not exist yet if created concurrently).
_PROFILES_PATH = Path(__file__).resolve().parents[1] / "schemas" / "dataset_type_profiles.yaml"

# ---------------------------------------------------------------------------
# Hardcoded marker sets (used as fallback when YAML file is absent)
# ---------------------------------------------------------------------------
DETECTION_COLUMN_MARKERS = {
    "video",
    "frame",
    "objectid",
    "object_id",
    "class",
    "x",
    "y",
    "width",
    "height",
    "confidence",
}
SENSOR_COLUMN_MARKERS = {
    "gazeforward",
    "gazeorigin",
    "leftpupildiameterinmm",
    "rightpupildiameterinmm",
    "leftirisdiameterinmm",
    "rightirisdiameterinmm",
    "projectedx",
    "projectedy",
    "quadlocalx",
    "quadlocaly",
    "pixelx",
    "pixely",
}
PROCESS_COLUMN_MARKERS = {
    "timestamp",
    "phase",
    "run",
    "ispareto",
    "framenumber",
    "capturetime",
    "logtime",
    "videoframe",
    "hmdposition",
    "hmdrotation",
    "unnamed0",
    "unnamed1",
}


def normalize_column_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", str(value).strip().lower())


# ---------------------------------------------------------------------------
# YAML-driven profiles loader
# ---------------------------------------------------------------------------

def _hardcoded_default_profiles() -> list[dict]:
    """Return profile list equivalent to the existing hardcoded classification logic."""
    return [
        {
            "id": DATASET_TYPE_DETECTION,
            "label": "Object Detection",
            "path_hints": ["yolo", "bbox", "bounding_box", "detection"],
            "markers": list(DETECTION_COLUMN_MARKERS),
            "min_marker_count": 5,
            "min_marker_ratio": 0.30,
            "schema": "standard_detection_mapping.yaml",
            "priority": 10,
        },
        {
            "id": DATASET_TYPE_SENSOR,
            "label": "Sensor Stream",
            "path_hints": [],
            "markers": list(SENSOR_COLUMN_MARKERS),
            "min_marker_count": 3,  # matches dataset_type_profiles.yaml
            "min_marker_ratio": 0.20,
            "schema": "standard_sensor_mapping.yaml",
            "priority": 9,
        },
        {
            "id": DATASET_TYPE_QUESTIONNAIRE,
            "label": "Questionnaire",
            "path_hints": ["questionnaire", "survey", "likert", "rating"],
            "markers": [],
            "min_question_hits": 3,
            "min_question_ratio": 0.50,
            "schema": "standard_dv_mapping.yaml",
            "priority": 7,
        },
        {
            "id": DATASET_TYPE_PROCESS,
            "label": "Process Log",
            "path_hints": [],
            "markers": list(PROCESS_COLUMN_MARKERS),
            "min_marker_count": 3,
            "min_marker_ratio": 0.30,
            "schema": "standard_metadata_mapping.yaml",
            "priority": 5,
        },
        {
            "id": DATASET_TYPE_RESULTS,
            "label": "Results Table",
            "path_hints": [],
            "markers": [],
            "min_marker_count": 0,
            "min_marker_ratio": 0.0,
            "schema": "standard_dv_mapping.yaml",
            "priority": 0,  # fallback
        },
    ]


@lru_cache(maxsize=1)
def load_dataset_type_profiles() -> list[dict]:
    """Load dataset type profiles from YAML, sorted by priority descending.

    Falls back to hardcoded defaults if the YAML file does not exist yet
    (supports concurrent creation by a parallel agent).
    """
    if not _PROFILES_PATH.exists():
        logger.warning(
            "dataset_type_profiles.yaml not found at '%s' — using hardcoded defaults",
            _PROFILES_PATH,
        )
        return _hardcoded_default_profiles()

    try:
        data = yaml.safe_load(_PROFILES_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to load dataset_type_profiles.yaml ('%s'): %s — using hardcoded defaults",
            _PROFILES_PATH,
            exc,
        )
        return _hardcoded_default_profiles()

    profiles = data.get("dataset_types", [])
    if not profiles:
        logger.warning(
            "dataset_type_profiles.yaml contained no 'dataset_types' entries — "
            "using hardcoded defaults"
        )
        return _hardcoded_default_profiles()

    return sorted(profiles, key=lambda p: p.get("priority", 0), reverse=True)


def get_schema_for_dataset_type(dataset_type_id: str) -> str:
    """Return the schema filename for a given dataset type ID.

    Loads from profiles YAML (or hardcoded fallback).  Returns the standard DV
    mapping schema as a safe default when the type is unknown.
    """
    for profile in load_dataset_type_profiles():
        if profile.get("id") == dataset_type_id:
            return profile.get("schema", "standard_dv_mapping.yaml")
    return "standard_dv_mapping.yaml"


# ---------------------------------------------------------------------------
# Dataset type classifier
# ---------------------------------------------------------------------------

def classify_dataset_type(relative_path: Path, column_names: Iterable[str]) -> str:
    """Classify a dataset file into one of the known dataset types.

    Uses YAML-driven profiles (falling back to hardcoded defaults when the
    profiles YAML file does not exist).  Profiles are evaluated in descending
    priority order; the first matching profile wins.

    Public API is unchanged: same signature and same return values as before.
    """
    profiles = load_dataset_type_profiles()
    from pathlib import Path as _Path
    _p = _Path(relative_path) if not isinstance(relative_path, _Path) else relative_path
    path_text = _p.as_posix().lower()
    raw_columns = [str(c) for c in column_names]
    normalized_columns = {normalize_column_name(c) for c in raw_columns}
    total_columns = max(len(raw_columns), 1)

    for profile in profiles:
        pid = profile.get("id", "")
        path_hints: list[str] = profile.get("path_hints", []) or []
        markers: list[str] = profile.get("markers", []) or []
        min_marker_count: int = profile.get("min_marker_count", 0)
        min_marker_ratio: float = float(profile.get("min_marker_ratio", 0.0))

        # Results table (priority 0) is the unconditional fallback.
        if pid == DATASET_TYPE_RESULTS:
            return DATASET_TYPE_RESULTS

        # Check path hints first (fast path).
        path_hint_match = any(hint in path_text for hint in path_hints if hint)

        if pid == DATASET_TYPE_QUESTIONNAIRE:
            # Special questionnaire detection logic: long names, '?' suffix,
            # starts with question words.
            min_q_hits: int = profile.get("min_question_hits", 3)
            min_q_ratio: float = float(profile.get("min_question_ratio", 0.50))
            question_hits = sum(
                1
                for col in raw_columns
                if "?" in col
                or len(col.strip()) >= 50
                or col.strip().lower().startswith(("what ", "which ", "how ", "i "))
            )
            question_ratio = question_hits / total_columns
            threshold = max(min_q_hits, total_columns // 2)
            if path_hint_match or (question_hits >= threshold and question_ratio >= min_q_ratio):
                return DATASET_TYPE_QUESTIONNAIRE
            continue

        # Marker-based detection for all other types.
        marker_set = {normalize_column_name(m) for m in markers}
        hits = len(normalized_columns & marker_set)
        ratio = hits / total_columns

        if path_hint_match or (hits >= min_marker_count and ratio >= min_marker_ratio):
            return pid

    # Should not be reached (results_table profile handles the fallback above),
    # but provide a safety net.
    return DATASET_TYPE_RESULTS


def infer_mapping_domain(
    canonical_name: str,
    mapping_status: str,
    canonical_domain_lookup: dict[str, str],
    mapping_source: str | None = None,
) -> str:
    if mapping_status == "blocked":
        return MAPPING_DOMAIN_BLOCKED
    if mapping_status == "unmapped":
        return MAPPING_DOMAIN_UNMAPPED

    domain = canonical_domain_lookup.get(str(canonical_name))
    if domain:
        return domain

    if mapping_source and mapping_source not in {"llm_deduction", "in_memory_mapping"}:
        return MAPPING_DOMAIN_CUSTOM

    return MAPPING_DOMAIN_CUSTOM
