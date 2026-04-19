# System Architecture

## Overview
The tool is a layered pipeline. Each layer has one entry script and can be used on its own:

1. **Schema layer** (`schemas/`). YAML files describe canonical DV names, sensor streams, object-detection fields, and metadata/process columns. `scripts/schema_utils.py` flattens and validates them; `scripts/validate_schema.py` is a standalone sanity check.
2. **Single-file conversion** (`scripts/convert_dv.py`). Reads a `.csv`/`.xlsx`, classifies the dataset type, applies the relevant schema family, and writes a standardized file (+ optional sidecars: `_metadata.json`, `_schema_suggestions.yaml`, `*-quality.json`).
3. **Batch standardization** (`scripts/run_batch_standardization.py`). Iterates a manifest of sources (`local_path`, `github_repo`, `osf_project`, `web_dataset`), downloads/extracts archives, runs conversion per dataset, and writes cross-source artifacts: `meta_view.csv/json`, `run_summary.json`, `unknown_alias_summary.json`, `mapping_debug_summary.json`. Optional local LLM deduction (`scripts/llm_utils.py`) is a fallback after explicit mappings.
4. **Catalog orchestrator** (`scripts/run_catalog_meta_analysis.py`). Reads a CSV/Excel catalog of dataset URLs, deduplicates, generates a manifest, invokes batch standardization, then runs the cross-study meta-analysis.
5. **Multi-study analysis** (`analyses/multi_study_analysis.py`). Consumes the `standardized/` tree produced above. Computes DV overlap, harmonized per-(study, DV) summaries, random-effects pooled estimates, standardized study-vs-pool deviations, a cross-study composite, and LiNGAM causal discovery. Uses `meta_view.csv` for mapping-provenance categories (`schema` / `repo_mapping` / `llm_deduced` / `blocked` / `unknown`) and supports sensitivity passes via `--exclude-llm-deduced`.
6. **UI layer** (`ui/`). Streamlit app covering single-file standardization and catalog-driven exploration of overlap/meta-analysis artifacts.

## Provenance and fallbacks
At every boundary the pipeline records *why* each value exists:

- **Alias resolution**: `mapping_source` per (source_id, canonical_dv) in `meta_view.csv` — `schema`, `repo_mapping`, `llm_deduced`, or `blocked`.
- **Source availability**: `run_summary.json` statuses include `ok`, `not_available`, `access_restricted` (e.g. Cloudflare-blocked ACM downloads), and `failed`.
- **Meta-analysis pool membership**: `meta_analysis_summary.csv` columns `mapping_source_categories`, `k_llm_deduced`, `includes_llm_deduced` flag pooled estimates that lean on LLM inference.
- **Causal discovery**: `discover_causal_structure` reports `used_method` ∈ {`complete_case`, `clique_complete_case`, `synthetic_cholesky`} and a `synthetic_fallback` flag.

## Technologies Used
- YAML for schema and manifest representation
- Python (pandas, numpy, matplotlib, seaborn, pydantic) for transformation and analysis
- Optional `transformers` + `torch` for local LLM deduction (`requirements-llm.txt`)
- Optional `streamlit` for the UI (`requirements-ui.txt`)
- Unittest / pytest suite under `tests/`

## Example end-to-end flow
**Input**: `data/raw/study_catalog_example.csv`
```
python scripts/run_catalog_meta_analysis.py \
  --catalog data/raw/study_catalog_example.csv \
  --url-column dataset_url \
  --source-id-column study_name \
  --source-type-column source_type \
  --output-dir data/processed/catalog_meta_analysis
```
**Output**:
- `generated_sources_manifest.yaml` + `catalog_source_summary.csv`
- `standardized/<source_id>/*-standardized.csv` per ingested study
- `meta_view.csv` (mapping provenance)
- `analysis/meta_analysis_summary.csv`, `dv_overlap_matrix.csv`, `dv_presence_matrix.csv`, `dv_overlap_details.csv`, `study_vs_pool_standardized_deviation.csv`
- `analysis/*_llm_excluded.csv` sensitivity siblings when any LLM-deduced rows are present
