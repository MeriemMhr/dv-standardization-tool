# Usage Workflows

This guide walks you through practical ways to run the DV Standardization Tool using scripts, folders, notebooks, and the UI components.


## Easy Start (Beginner Path)

If you are completely new, use this minimal path first:

1. Put a single dataset file in `data/raw/` (for example `my_study.csv`).
2. Create a small YAML mapping file (for example `data/raw/my_mapping.yaml`) with canonical IDs mapped to your local aliases:

```yaml
task_completion_time:
  - completion_time
  - taskTime

user_satisfaction:
  - sus_score
  - subjective_rating
```

3. Run the converter:

```bash
python scripts/convert_dv.py \
  --input data/raw/my_study.csv \
  --schema data/raw/my_mapping.yaml \
  --output data/processed/my_study-standardized.csv
```

4. If you want guidance for unmapped columns, rerun with metadata output:

```bash
python scripts/convert_dv.py \
  --input data/raw/my_study.csv \
  --schema data/raw/my_mapping.yaml \
  --output data/processed/my_study-standardized.csv \
  --with-metadata
```

This produces sidecars like `*_metadata.json` and `*_schema_suggestions.yaml` so you can quickly improve your YAML aliases.

### Where LLM inference is used

LLM-assisted alias deduction is used in `scripts/run_batch_standardization.py` when a source does not include its own mapping YAML. In that case, the pipeline attempts to infer likely canonical IDs for unknown aliases using local model candidates and repository context (README/PDF text).

### Easy batch processing example (beginner)

Create a manifest file `data/raw/my_sources_manifest.yaml`:

```yaml
sources:
  - source_id: my_local_study_folder
    source_type: local_path
    location: data/raw/my_batch_folder
    include_globs:
      - "**/*.csv"
      - "**/*.xlsx"
      - "**/*.xls"
      - "**/*.tsv"
```

Then run:

```bash
python scripts/run_batch_standardization.py \
  --manifest data/raw/my_sources_manifest.yaml \
  --output-dir data/processed/batch_runs/my_first_batch \
  --snapshot-manifest
```

Expected outputs:
- `meta_view.csv` and `meta_view.json` (combined harmonized summary)
- `run_summary.json` (run-level status/provenance)
- `standardized/my_local_study_folder/*-standardized.*`
- per-dataset quality sidecars (`*-quality.json`)

## General Workflow

1. Upload or locate a dataset (`ui/components/uploader.py` for UI mode, local files for CLI mode).
2. Preview columns (`ui/components/column_preview.py`).
3. Apply DV mapping (`scripts/convert_dv.py`).
4. Validate mapping (`scripts/validate_schema.py`, `notebooks/visual_validation.ipynb`).
5. Export results (`ui/components/download_button.py` or CLI output files).
6. Review unknown/unmapped columns and propose additions to `schemas/standard_dv_mapping.yaml` in a pull request.

---

## Script-based Workflows (Recommended for reproducibility)

### 1) Basic single-file workflow

```bash
python scripts/convert_dv.py \
  --input data/raw/raw_sample_roads_chi25.xlsx \
  --output data/processed/processed_sample_roads_chi25.xlsx
```

Use this when you already know the input and output file paths.

### 2) Folder-based workflow (auto-discovery)

If your folder contains exactly one input file (`.csv`, `.xlsx`, or `.xls`), you can pass the folder directly:

```bash
python scripts/convert_dv.py --input data/raw
```

Behavior in folder mode:
- Input file: auto-detected when exactly one tabular file exists.
- Schema file: if no `--schema` is provided, the script uses:
  1. exactly one `.yaml`/`.yml` in that folder, otherwise
  2. fallback to `schemas/standard_dv_mapping.yaml`.
- Output file: defaults to `<input-stem>-standardized.<ext>` in the same folder unless `--output` is provided.

### 3) Folder-based workflow with explicit output

```bash
python scripts/convert_dv.py \
  --input data/raw \
  --output data/processed/roads-standardized.xlsx
```

This is useful when you want to keep standardized files in a dedicated output directory.

### 4) Custom schema + standard schema priority (extensible behavior)

```bash
python scripts/convert_dv.py \
  --input data/raw/raw_sample_roads_chi25.xlsx \
  --schema schemas/example_alias_submissions.yaml \
  --output data/processed/roads-standardized-from-custom.xlsx
```

When a custom schema is provided:
- The tool includes **both** mappings from the selected custom schema and from `schemas/standard_dv_mapping.yaml`.
- Alias collisions are controlled by `--alias-conflict-policy`:
  - `prefer_standard` (default): standard mapping wins and preserves canonical IDs.
  - `prefer_custom`: custom mapping wins for conflicting aliases.
  - `error`: abort if any conflicts are detected.
- The custom schema still extends coverage for additional aliases not yet in the standard mapping.

### 5) Metadata inference workflow

```bash
python scripts/convert_dv.py \
  --input data/raw/raw_sample_roads_chi25.xlsx \
  --output data/processed/roads-standardized-with-meta.xlsx \
  --with-metadata
```

This also exports a sidecar JSON file named `<output_stem>_metadata.json` including:
- inferred measurement metadata,
- review flags, and
- unknown columns with a recommendation to propose those aliases to the standard mapping via pull request,
- and a generated `<output_stem>_schema_suggestions.yaml` template you can copy into your PR.

---

## Notebook-based Usage

- **`notebooks/prototype_notebook.ipynb`**: Test conversion logic and validate transformations step-by-step.
- **`notebooks/schema_builder.ipynb`**: Iteratively define or revise `schemas/standard_dv_mapping.yaml`.
- **`notebooks/visual_validation.ipynb`**: Visually compare pre/post mapping outcomes.
- **`notebooks/llm_inference_prototype.ipynb`** _(Optional)_: Explore semantic matching and future LLM-assisted schema extension.

---

## Practical Maintenance Workflow for Mapping Quality

1. Run conversion on a new dataset.
2. Check CLI warnings, metadata sidecar, and generated `_schema_suggestions.yaml` template for unknown columns.
3. If an unknown alias is semantically valid and recurring, add it to `schemas/standard_dv_mapping.yaml`.
4. Submit the schema update as a pull request so future conversions improve automatically.

This keeps mappings consistent while still allowing the schema to evolve with new studies and domain-specific terminology.
