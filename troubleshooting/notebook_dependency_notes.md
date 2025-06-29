# Notebook-Script Interoperability Notes

This document outlines known interdependencies between Jupyter notebooks and Python scripts within the DV Standardization Tool project. It helps maintain reproducibility and alerts future contributors to areas where changes in one file may break another.

---

## Overview

Each notebook draws on one or more core Python modules, YAML schemas, or specific I/O paths. Without synchronized logic or consistent schema loading, discrepancies may occur—especially during prototyping or partial execution.

---

## Known Interdependencies

### 1. **`prototype_notebook.ipynb`**

- **Relies on**:
  - `scripts/convert_dv.py`
  - `schemas/standard_dv_mapping.yaml`
- **Common Issues**:
  - Schema edits not reflected until notebook is restarted
  - Cached cells masking changes in I/O logic

**Tip**: Always restart the notebook kernel after editing scripts.

---

### 2. **`visual_validation.ipynb`**

- **Relies on**:
  - `scripts/visual_helpers.py`
  - Matching number of columns before/after transformation
- **Common Issues**:
  - Visualization errors if schema drops or adds columns
  - Use of outdated schema or missing `processed/` files

**Tip**: Run `convert_dv.py` in advance and cache the output before launching this notebook.

---

### 3. **`llm_inference_prototype.ipynb`**

- **Relies on**:
  - `scripts/llm_utils.py`
  - `schemas/schema_meta.yaml` (for prompt structuring)
- **Common Issues**:
  - Mismatches between column names and prompt expectations
  - Token limits when using large schema descriptions

**Tip**: Use filtered/trimmed prompts and load schema metadata dynamically.

---

### 4. **`schema_builder.ipynb`**

- **Relies on**:
  - `scripts/schema_utils.py`
- **Common Issues**:
  - Manual updates to schema not synced with UI or validation tools
  - Structure of YAML file broken due to incorrect appends

**Tip**: Always validate your YAML schema after edits using `validate_schema.py`.

---

## General Recommendations

- Use relative paths consistently across notebooks and scripts
- Clear outputs and restart kernels before committing notebooks
- Validate schema changes with both CLI (`validate_schema.py`) and notebook previews
- Maintain modular function imports in notebooks to avoid duplication

---

Please report any reproducibility issues via GitHub Issues for transparent tracking.
