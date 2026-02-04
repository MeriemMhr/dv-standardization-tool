# OpenDV-HCI v2.1: New Features

## 🎯 What's New

Version 2.1 introduces **measurement metadata inference** capabilities, enabling the tool to automatically classify dependent variables by their measurement properties (category, units, scale type) in addition to standardizing their names.

### Key Enhancements

#### 1. **Measurement Category Taxonomy**

DVs are now automatically classified into 8 broad measurement categories:

- **Time**: Duration/latency measurements (seconds, milliseconds, minutes)
- **Accuracy**: Correctness/error measures (percentage, proportion)
- **Count**: Discrete occurrences (integer counts, frequencies)
- **Likert**: Ordinal rating scales (5-point, 7-point, NASA-TLX, SUS, etc.)
- **Proportion**: Ratios and percentages
- **Binary**: Success/failure, yes/no outcomes
- **Continuous**: Unbounded numeric measures
- **Physiological**: Biometric signals (EDA, HR, pupil dilation, etc.)

#### 2. **Automatic Metadata Inference**

The tool now uses heuristic rules to infer:
- **Category**: What type of measure (Time, Likert, etc.)
- **Primary Unit**: The preferred unit for standardization
- **Scale Type**: Stevens' typology (nominal, ordinal, interval, ratio)
- **Direction**: Interpretation (higher_is_better, lower_is_better, neutral)
- **Confidence Score**: How certain the inference is (0.0-1.0)

#### 3. **Meta-Analysis Ready Output**

Standardized DVs now include metadata that enables:
- Cross-study aggregation with proper unit conversion
- Appropriate statistical methods based on scale type
- Detection of inverted scales (e.g., error rate vs. accuracy)
- Instrument recognition (NASA-TLX, SUS, UEQ, SAM, PANAS, etc.)

---

## 📁 New Files Added

### Schemas
- `measurement_categories.yaml` - Taxonomy of 8 measurement categories with aggregation rules
- `inference_rules.yaml` - Heuristic rules for automatic category/unit inference

### Scripts
- `measurement_types.py` - Data structures for measurement metadata
- `dv_inference.py` - Core inference logic with confidence scoring

### Updated Files
- `standard_dv_mapping.yaml` - Extended with `measurement` field for each DV (now v2.1)
- `convert_dv.py` - New `--with-metadata` flag for metadata inference
- `schema_utils.py` - Extended with measurement metadata utilities
- `validate_schema.py` - Now validates measurement metadata fields

---

## 🚀 Updated Usage

### Basic Usage (Column Renaming Only)

```bash
python scripts/convert_dv.py \
  --input data/raw/sample.csv \
  --output data/processed/standardized.csv
```

### With Measurement Metadata Inference (NEW)

```bash
python scripts/convert_dv.py \
  --input data/raw/sample.csv \
  --output data/processed/standardized.csv \
  --with-metadata
```

This generates two files:
1. `standardized.csv` - The standardized data
2. `standardized_metadata.json` - Measurement metadata for each column

### Example Metadata Output

```json
{
  "schema_version": "2.1",
  "inference_timestamp": "2026-02-04T15:30:00",
  "columns": {
    "task_completion_time": {
      "category": "Time",
      "primary_unit": "seconds",
      "allowed_units": ["s", "ms", "min"],
      "scale_type": "ratio",
      "direction": "lower_is_better",
      "confidence": 0.95,
      "inferred": false,
      "matched_rules": ["schema_defined"],
      "needs_review": false,
      "original_name": ["time_spent", "completion_duration"]
    },
    "sus_score": {
      "category": "Likert",
      "primary_unit": "100-point",
      "scale_type": "interval",
      "direction": "higher_is_better",
      "confidence": 0.95,
      "inferred": true,
      "matched_rules": ["instrument:SUS"],
      "needs_review": false,
      "original_name": ["system_usability_scale"]
    }
  },
  "summary": {
    "total_columns": 15,
    "needs_review": 2,
    "categories": {
      "Time": 3,
      "Likert": 5,
      "Accuracy": 2,
      "Count": 3,
      "Physiological": 2
    }
  }
}
```

---

## 📊 Schema Format (v2.1)

### Extended DV Entry Structure

```yaml
- id: task_completion_time
  label: "Task Completion Time"
  cluster: performance

  # NEW: Measurement metadata block
  measurement:
    category: Time
    primary_unit: seconds
    allowed_units: [s, ms, min]
    scale_type: ratio
    direction: lower_is_better

  aliases:
    - time_spent
    - completion_duration
    - task_time
  instruments: []
  units: ["s", "ms"]
  notes: "Report central tendency + dispersion."
```

---

## 🧪 Validation

Validate your schema with measurement metadata:

```bash
python scripts/validate_schema.py schemas/standard_dv_mapping.yaml
```

Output:
```
============================================================
OpenDV-HCI Schema Validator
============================================================
Validating: schemas/standard_dv_mapping.yaml

Schema version: 2.1
Format: New format (v2.1+)

✓ Schema is valid!

Summary:
  - Total DVs: 24
  - Total aliases: 120
  - DVs with measurement metadata: 24/24
```

---

## 🎯 Confidence Scoring

Inferences include confidence scores to flag uncertain classifications:

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| 0.90 – 1.00 | High confidence (instrument/schema match) | Auto-accept |
| 0.70 – 0.89 | Good confidence (multiple rule matches) | Auto-accept with logging |
| 0.50 – 0.69 | Moderate confidence (single rule match) | Flag for optional review |
| 0.30 – 0.49 | Low confidence (weak match) | Require human review |
| < 0.30 | Very low confidence (fallback) | Manual classification required |

Columns with `needs_review: true` are flagged in the output for manual inspection.

---

## 🔬 Research Benefits

### For Meta-Analysis

- **Unit Conversion**: Time measures in ms/s/min can be pooled after conversion
- **Scale Type Awareness**: Ordinal vs. ratio determines appropriate statistics
- **Direction Handling**: Detect inverted scales (accuracy vs. error rate)
- **Instrument Recognition**: Known scales (NASA-TLX, SUS) mapped automatically

### For Reproducibility

- **Machine-Readable Metadata**: JSON sidecar enables programmatic analysis
- **FAIR Compliance**: Structured metadata supports Findable, Accessible, Interoperable, Reusable principles
- **Audit Trail**: Confidence scores and matched rules document inference process
- **Community Extension**: New categories/rules can be added via YAML files

---

## 📖 Additional Documentation

- [Measurement Categories Reference](measurement_categories.yaml)
- [Inference Rules Specification](inference_rules.yaml)
- [API Documentation](../scripts/dv_inference.py)
- [Implementation Report](../OpenDV_HCI_Tool_Assessment_Analysis.pdf)

---

## 🤝 Contributing

Contributions to extend measurement categories or improve inference rules are welcome! See:
- `schemas/example_alias_submissions.yaml` for contribution templates
- `.github/ISSUE_TEMPLATE/contribution-suggestion.md` for guidelines

---

## 📝 Version History

### v2.1 (2026-02-04)
- Added measurement metadata inference
- Introduced 8-category taxonomy
- Extended schema with `measurement` fields
- Added `--with-metadata` flag to converter
- Created `measurement_types.py` and `dv_inference.py` modules
- Enhanced schema validation for measurement metadata

### v2.0 (2025-09-07)
- Restructured schema to list-based format with `dvs` key
- Added cluster-based organization
- Enhanced validation rules

### v0.1 (2025-06-29)
- Initial release with basic alias mapping
- YAML-driven conversion pipeline
