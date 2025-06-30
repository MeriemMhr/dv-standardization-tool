# Dataset Upload & Anonymization Guidelines

## Sourcing Data

* Prioritize publicly available HCI datasets shared through ACM Digital Library, OSF, or repositories with DOI support.
* Ensure data contain relevant DV fields with some inconsistencies for transformation testing.

## Upload Protocol

1. Use `data/raw/` for unprocessed datasets
2. Upload corresponding `schema.yaml` under `schemas/`
3. Add logs in `logs/` after running the tool

## Anonymization

* No personally identifiable information (PII) must be present in uploaded data
* Fields like `participant_id`, `email`, or `free_text_response` should be:

  * Removed
  * Pseudonymized
  * Or flagged in schema via `sensitive: true`

## Sample Workflow

```
raw_dataset.csv → anonymize → schema.yaml → convert → standardized_output.csv
```
