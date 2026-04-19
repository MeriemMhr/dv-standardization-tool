# Repository Changelog

This document logs human-readable updates to the repo's functionality, structure, and features.

---

### [2026-04-19]

- **Meta-analysis provenance tracking.** `harmonized_dv_summary.csv` now includes a `mapping_source` column (`schema` / `repo_mapping` / `llm_deduced` / `blocked` / `unknown`). `meta_analysis_summary.csv` gains `estimator`, `mapping_source_categories`, `k_llm_deduced`, and `includes_llm_deduced` to make it easy to flag pooled estimates that depend on LLM inferences.
- **Sensitivity analysis flag.** `analyses/multi_study_analysis.py` adds `--exclude-llm-deduced`, which writes `harmonized_dv_summary_llm_excluded.csv`, `meta_analysis_summary_llm_excluded.csv`, and `study_vs_pool_standardized_deviation_llm_excluded.csv`. The catalog orchestrator (`scripts/run_catalog_meta_analysis.py`) emits these automatically whenever any LLM-deduced rows are present.
- **Causal discovery transparency.** `discover_causal_structure` now reports `used_method` (`complete_case` / `clique_complete_case` / `synthetic_cholesky`), `n_complete_rows`, and `synthetic_fallback`. Passing `refuse_synthetic=True` (CLI: `--refuse-synthetic-causal`) blocks the Cholesky-synthesized fallback.
- **Renamed study-vs-pool effects output.** The legacy `standardized_effects.csv` is preserved for backward compatibility, and a clearer `study_vs_pool_standardized_deviation.csv` is now also emitted to make clear that the value is a descriptive standardized distance from the pooled mean, not a contrast-based Hedges' g.
- **Additional catalog sources.** The example catalog and `sources_manifest_example.yaml` now include the Touch-Interaction-with-Road-Bumps GitHub dataset, 4TU's critical-eHMI article, and the ACM CHI 2026 supplemental ZIP. ACM downloads behind Cloudflare are now recorded as `access_restricted` rather than `failed`.

---

### [2024-07-01]

- Added `ui/` interface with uploader, download button, and column preview
- Created full schema suite: `standard_dv_mapping.yaml`, `schema_meta.yaml`, etc.
- Prototyped LLM-based suggestions via `scripts/llm_utils.py`
- Established full pipeline validation through `convert_dv.py` and `visual_validation.ipynb`
- Populated the `docs/` directory for transparency

Schema-specific updates: see `schemas/schema_changelog.yaml`
