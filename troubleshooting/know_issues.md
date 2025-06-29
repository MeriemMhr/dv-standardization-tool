# Known Issues and Troubleshooting Guide

This document tracks known issues encountered during the use and development of the DV Standardization Tool, along with suggested explanations and workarounds. It is intended as a living file to support reproducibility and collaboration.

---

## 1. Column Not Found in Schema Mapping

**Symptom**:  
`KeyError` or `NoneType` during execution of `convert_dv.py`.

**Cause**:  
The dataset contains a column name not listed in `standard_dv_mapping.yaml`.

**Resolution**:  
- Check the unrecognized column name in the raw dataset.
- If relevant, add a new alias to the mapping under the appropriate standardized term.
- Validate schema changes using `validate_schema.py`.

---

## 2. Jupyter Notebook Output Mismatch

**Symptom**:  
The processed dataframe preview doesn't match expected column names after transformation.

**Cause**:  
The mapping logic in `convert_dv.py` is outdated or was overwritten manually.

**Resolution**:  
- Ensure the `.yaml` file used matches the one loaded in the notebook.
- Re-run the notebook from the top.
- Consider using a fixed version of the schema (via a snapshot or `schema_changelog.yaml` entry).

---

## 3. Fuzzy Matching Produces Incorrect Substitutions

**Symptom**:  
Column `completion_rate` is incorrectly standardized to `task_completion_time`.

**Cause**:  
Overlapping similarity thresholds or imprecise alias entries.

**Resolution**:  
- Adjust or remove ambiguous aliases in `standard_dv_mapping.yaml`.
- Lower fuzzy confidence thresholds in future updates of `convert_dv.py`.
- Consider manually overriding ambiguous mappings for edge cases.

---

## 4. LLM Prototype Fails to Infer Contextually Accurate Mappings

**Symptom**:  
`llm_inference_prototype.ipynb` suggests irrelevant or hallucinated mappings.

**Cause**:  
Prompting is too generic or lacks grounding in schema metadata.

**Resolution**:  
- Fine-tune the prompt templates.
- Integrate schema constraints via `schema_meta.yaml` or in-context examples.
- Use smaller, domain-specific datasets for inference.

---

## 5. Streamlit App Upload Produces Blank Preview

**Symptom**:  
File uploads, but preview window remains empty.

**Cause**:  
- Malformed CSV structure.
- Column names not passed correctly from `uploader.py` to `column_preview.py`.

**Resolution**:  
- Verify that the CSV contains a header row.
- Log the DataFrame shape and columns in the sidebar for debugging.
- Ensure UTF-8 encoding is preserved.
