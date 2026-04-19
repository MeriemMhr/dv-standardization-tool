# Multi-Study Analysis Guide (After DV Standardization)

This guide shows how to analyze **multiple standardized datasets** even when independent variables are unavailable, inconsistent, or poorly documented.

## Why these analyses are useful without IVs
When studies share standardized dependent variable (DV) names, you can still do meaningful cross-study work:

1. **Coverage/compatibility analysis**: quantify how much the studies can be compared (DV overlap).
2. **Outcome benchmarking**: compare study-level performance on shared outcomes.
3. **Cross-study latent construct extraction**: build a pooled composite score from common DVs.
4. **Random-effects DV meta-analysis**: estimate pooled means and heterogeneity for shared DVs.

## Getting standardized datasets to analyze
The multi-study analysis expects a folder of already-standardized study files (one `.csv` or `.xlsx` per study). There are two supported starting points:

1. **Run the batch pipeline first** (recommended). Any of the workflows below produces a `standardized/<source_id>/` tree that can be fed in directly:
   - `python scripts/run_batch_standardization.py --manifest sources_manifest_example.yaml --output-dir data/processed/batch_runs/latest`
   - `python scripts/run_catalog_meta_analysis.py --catalog data/raw/study_catalog_example.csv ...` (this already invokes the meta-analysis automatically on the produced datasets).
2. **Use pre-standardized files of your own**. Put one standardized file per study into a single folder and point `--input-dir` at it.

The `data/processed/` tree is gitignored, so it does not ship with pre-computed example outputs. The repository's `data/raw/study_catalog_example.csv` together with `sources_manifest_example.yaml` are the canonical reproducible starting points.

## Python workflow
Script: `analyses/multi_study_analysis.py`

### Install latest packages
```bash
python -m pip install --upgrade pip
python -m pip install --upgrade pandas numpy matplotlib seaborn scikit-learn openpyxl
```

### Run
```bash
python analyses/multi_study_analysis.py \
  --input-dir data/processed/batch_runs/latest/standardized \
  --output-dir analyses/output_python
```

### CLI options at a glance

| flag | default | meaning |
| --- | --- | --- |
| `--input-dir` | `data/processed/multi_study_examples` | Folder containing standardized study files. If you used the batch runner, point at its `standardized/` subdirectory. |
| `--output-dir` | `analyses/output_python` | Where the CSVs and plots are written. |
| `--estimator {DL,REML}` | `DL` | Tau-squared estimator used by the random-effects meta-analysis. |
| `--harmonize-scales` / `--no-harmonize-scales` | on | Whether to rescale DVs to canonical ranges before pooling. |
| `--repeated-measures k1,k2,...` | (empty) | Comma-separated study keys to aggregate to participant-level means before pooling. |
| `--exclude-llm-deduced` | off | Sensitivity pass that drops LLM-deduced rows; emits `*_llm_excluded.csv` siblings. |
| `--meta-view path` | `<input-dir>/../meta_view.csv` | Source of mapping-provenance categories. |
| `--refuse-synthetic-causal` | off | Block the Cholesky-synthesized fallback inside LiNGAM causal discovery. |

### Run on the latest standardized batch output
Use this helper script to automatically pick up everything in
`data/processed/batch_runs/latest/standardized`. If that folder is missing, the
script falls back to `data/processed/multi_study_examples` — useful if you have
cached local example files there, otherwise run the batch pipeline first.

```bash
bash analyses/run_latest_multi_study_analysis.sh
```

Optional custom output directory:

```bash
bash analyses/run_latest_multi_study_analysis.sh analyses/output_python_latest_standardized
```

### Outputs
- `analyses/output_python/dv_overlap_matrix.csv`
- `analyses/output_python/harmonized_dv_summary.csv` — per-(study, canonical DV) row-level summary. Now includes a `mapping_source` column with values `schema`, `repo_mapping`, `llm_deduced`, `blocked`, or `unknown`.
- `analyses/output_python/meta_analysis_summary.csv` — random-effects pooled estimates per canonical DV. New columns: `estimator` (DL / REML), `mapping_source_categories`, `k_llm_deduced`, `includes_llm_deduced`.
- `analyses/output_python/standardized_effects.csv` — legacy alias, preserved for backward compatibility.
- `analyses/output_python/study_vs_pool_standardized_deviation.csv` — descriptive standardized distance between each study mean and the pooled mean. Renamed (and documented) to avoid being mistaken for a contrast-based Hedges' g effect size.
- `analyses/output_python/cross_study_composite_summary.csv`
- `analyses/output_python/dv_overlap_heatmap.png`
- `analyses/output_python/dv_mean_shift.png`
- `analyses/output_python/dv_coverage_by_study.png`
- `analyses/output_python/cross_study_composite_distribution.png`

### Provenance tracking and sensitivity analysis
`run_batch_standardization.py` writes a per-(source_id, canonical DV) provenance trace to `meta_view.csv`. Multi-study analysis now loads this file automatically to stamp each harmonized row with a `mapping_source` category:

| category        | origin                                                            |
| --------------- | ----------------------------------------------------------------- |
| `schema`        | In-memory alias / shipped schema files                             |
| `repo_mapping`  | Repository-specific `mapping.yaml` overrides                       |
| `llm_deduced`   | A local LLM inferred the mapping                                   |
| `blocked`       | Never-map blocklist applied                                        |
| `unknown`       | No provenance available (e.g., ad-hoc input folder)                |

Use these CLI flags for sensitivity runs:

```bash
# Re-run meta-analysis without LLM-deduced rows and write _llm_excluded.csv siblings.
python analyses/multi_study_analysis.py \
  --input-dir data/processed/batch_runs/latest/standardized \
  --output-dir analyses/output_python \
  --exclude-llm-deduced

# Point at a non-default provenance file.
python analyses/multi_study_analysis.py --meta-view path/to/meta_view.csv ...

# Refuse the synthetic Cholesky fallback in LiNGAM causal discovery.
python analyses/multi_study_analysis.py --refuse-synthetic-causal ...
```

When `--exclude-llm-deduced` is set, three additional files are emitted:
- `harmonized_dv_summary_llm_excluded.csv`
- `meta_analysis_summary_llm_excluded.csv`
- `study_vs_pool_standardized_deviation_llm_excluded.csv`

The `scripts/run_catalog_meta_analysis.py` orchestrator also writes the `_llm_excluded` variants automatically whenever any LLM-deduced rows are present.

### Causal discovery fallback
`discover_causal_structure` reports `used_method` (one of `complete_case`, `clique_complete_case`, `synthetic_cholesky`) and a boolean `synthetic_fallback`. When rows are scarce the old behavior synthesized rows from the observed correlation matrix via Cholesky factorization; this is still available but is now labeled and logged as a warning. Pass `refuse_synthetic=True` (or `--refuse-synthetic-causal` on the CLI) to skip the synthetic fallback entirely.

## R workflow
> **Status:** planned. A matching `analyses/multi_study_analysis.R` is on the roadmap (see `docs/future_plans.md`) but is not yet shipped in this repository. If you need R today, export `harmonized_dv_summary.csv` from the Python workflow and read it into your preferred meta-analysis package (`metafor`, `meta`, `tidymeta`, etc.).

## Applying to your own standardized studies
1. Put each standardized dataset (`.csv` or `.xlsx`) into one folder.
2. Ensure DV columns are numeric and consistently named using the schema.
3. Run `python analyses/multi_study_analysis.py --input-dir <folder>` against it.
4. Inspect the DV overlap outputs first; if overlap is weak, restrict to the best-shared subset and rerun.


## Derived score auto-calculation
The Python analysis script auto-calculates common questionnaire scores when all required item-level columns are available (including mapped aliases):

- **NASA-TLX composite** (`nasa_tlx_score`) from six TLX subscales/items
- **SUS composite** (`sus_score`) from `sus1`..`sus10` (with alternating reverse coding)
- **van der Laan AOA subscales**:
  - `aoa_usefulness` from `aoa1, aoa3, aoa5, aoa7, aoa9`
  - `aoa_satisfying` from `aoa2, aoa4, aoa6, aoa8`

This uses standardized/mapped names when present (for example `mental_demand`, `physical_demand`, etc. for TLX items) so the calculations remain robust after DV standardization.

## Interpretation notes
- **High Jaccard overlap** indicates strong interoperability.
- **Mean z-shifts** highlight which studies are above/below pooled DV baselines.
- **Composite index** gives a common latent outcome for cross-study ranking/comparison.

This pattern is especially helpful for exploratory synthesis, preregistration planning, and power analysis preparation before full model-based meta-analysis.
