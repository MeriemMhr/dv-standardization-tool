# Schema–Dataset Misalignments: Diagnosis and Resolution

This document highlights frequent issues related to mismatches between the DV schema and incoming datasets. It supports accurate transformation workflows and promotes schema evolution based on real-world inconsistencies.

---

## Overview

The schema (`standard_dv_mapping.yaml`) maps known aliases to canonical dependent variable (DV) names. Misalignments typically emerge from:

- Poorly named or abbreviated DV labels in source datasets
- Inconsistent naming conventions (e.g., camelCase, snake_case, spacing)
- Context-dependent variables whose meaning is ambiguous without metadata
- Evolving terms that are not yet reflected in the schema

---

## Common Patterns and Fixes

### 1. **Undetected DV Variants**

**Example**: `avgSatisfaction` not recognized

**Fix**:
- Add to `user_satisfaction` aliases:
  ```yaml
  user_satisfaction:
    - avgSatisfaction
    - satisfaction_level````

---

### 2. **False Positives via Fuzzy Matching**

**Example**: `rating_score` incorrectly mapped to `task_completion_time`

**Fix**:

* Remove or reassign ambiguous terms from alias list.
* Lower fuzzy match confidence threshold or apply domain filtering.

---

### 3. **Inconsistent Capitalization or Formatting**

**Example**: `MentalLoad` not mapped due to PascalCase formatting.

**Fix**:

* Ensure column names are normalized (e.g., lowercased, stripped) before matching.
* Update pre-processing logic in `convert_dv.py`.

---

### 4. **Contextual Ambiguity**

**Example**: `performance_score` could refer to task accuracy or user satisfaction.

**Fix**:

* Manually assign based on dataset metadata or documentation.
* Flag such cases for LLM-based semantic inference (future extension).

---

### 5. **Missing Coverage in Schema**

**Example**: `trust_in_system` appears in dataset but not in any DV category.

**Fix**:

* If the construct is conceptually valid, add it as a new canonical DV.
* Document the decision in `schema_changelog.yaml`.

---

## Recommended Practices

* Always run schema validation (`validate_schema.py`) after edits.
* Update `schema_changelog.yaml` for transparency and version tracking.
* Use `example_alias_submissions.yaml` to capture proposed additions before integration.

---

Contributions to improve schema coverage and precision are welcome via GitHub Issues or pull requests.
