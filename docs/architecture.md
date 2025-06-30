# System Architecture

## Overview
The system consists of four key components:

1. **Schema Parser**: Validates and interprets YAML-based DV schema files.
2. **DV Conversion Engine**: Translates non-standard DV names to standardized names using predefined mapping logic.
3. **Trace Validator (Optional)**: Accepts trace-level inputs for debugging DV transformation workflows (`trace_convert_dv.txt`).
4. **Preview & Visualization Module** (in development): Interface to visualize broken schemas or DV collisions (see `broken_schema_preview_example.png`).

## Workflow
[Dataset Upload]
↓
[Schema Parser]
↓
[DV Conversion Engine]
↓
[Output: Standardized Dataset + Logs]

## Technologies Used
- YAML for schema representation
- Python (PyYAML, pandas) for transformation logic
- Markdown for documentation
- GitHub for version control

## Example Input–Output Flow
**Input**: `raw_dataset.csv` + `schema.yaml`  
**Output**: `standardized_dataset.csv` + `trace_convert_dv.txt`
