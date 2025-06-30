# Usage Workflows

This guide walks you through how to interact with the core components of the DV Standardization Tool using either the scripts or the notebooks.

## 🔁 General Workflow

1. Upload a dataset (`ui/components/uploader.py`)
2. Preview columns (`ui/components/column_preview.py`)
3. Apply DV mapping (`scripts/convert_dv.py`)
4. Validate mapping (`scripts/validate_schema.py`, `notebooks/visual_validation.ipynb`)
5. Export results (`ui/components/download_button.py`)

---

## 🧪 Notebook-based Usage

- **`prototype_notebook.ipynb`**: Ideal for testing logic and validating transformations.
- **`schema_builder.ipynb`**: Helps iteratively define/edit `standard_dv_mapping.yaml`.
- **`visual_validation.ipynb`**: Confirms alignment visually.
- **`llm_inference_prototype.ipynb`** _(Optional)_: Runs early-stage semantic matching via LLMs.

---

## 🛠 Script-based Usage

For CLI workflows or batch processing:

```bash
python scripts/convert_dv.py --input data/raw/sample.csv --output data/processed/mapped.csv
```

Useful for pipeline integrations or backend automation.