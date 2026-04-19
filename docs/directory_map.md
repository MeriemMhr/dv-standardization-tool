# Repository Directory Map

This document outlines the folder structure and purpose of each key directory.

```
.github/                 → GitHub workflow & community templates
analyses/                → Multi-study / cross-dataset analysis entrypoints
    multi_study_analysis.py          → Overlap, pooled means, meta-analysis, LiNGAM
    run_latest_multi_study_analysis.sh → Convenience runner against the latest batch output
data/
    raw/                 → Unprocessed CSVs and the example catalog file
    processed/           → Standardized datasets and batch outputs (gitignored)
docs/                    → Project documentation (this folder)
notebooks/               → Prototyping and testing notebooks
schemas/                 → Canonical and auxiliary YAML schemas
scripts/                 → Core CLI entrypoints (see table below)
tests/                   → Unittest / pytest suite for the pipeline
troubleshooting/         → Logs, mismatches, kernel and schema issues
ui/
    components/          → Streamlit helper scripts
    assets/              → CSS and logo for styling
sources_manifest_example.yaml → Example batch manifest covering GitHub / OSF / 4TU / ACM
```

## Key CLI entrypoints

| script | role |
| --- | --- |
| `scripts/convert_dv.py` | Standardize a single dataset against the schema(s). |
| `scripts/run_batch_standardization.py` | Standardize many sources from a manifest; writes `meta_view.csv` and per-source standardized trees. |
| `scripts/run_catalog_meta_analysis.py` | End-to-end: CSV/Excel catalog → batch standardization → meta-analysis artifacts. |
| `analyses/multi_study_analysis.py` | Overlap / pooled-mean / random-effects meta-analysis on a folder of standardized files. |
| `scripts/validate_schema.py` | Schema sanity check. |
| `ui/app.py` | Streamlit entry point (single-file + catalog modes). |
