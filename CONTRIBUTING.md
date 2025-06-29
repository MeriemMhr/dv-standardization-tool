## Contribution Guidelines
This repository is designed as a reproducible research artifact and welcomes community contributions aligned with responsible HCI research practices. Potential contributions include:

* Proposing new aliases or constructs for the DV naming scheme (`schemas/standard_dv_mapping.yaml`)
* Submitting anonymized datasets to test schema coverage and generalizability
* Suggesting enhancements (e.g., LLM-based variable inference, Streamlit UI components, visualization modules)
* Improving documentation or refactoring core logic (`convert_dv.py`)

To contribute, please fork the repository, follow the existing schema structure and coding conventions, and submit a pull request or open an issue. All contributions are reviewed with attention to transparency, traceability, and scholarly rigor.

**Lightweight issue (a) and pull request (b) templates are provided to streamline collaboration and maintain research transparency.**

#### a. `.github/ISSUE_TEMPLATE/contribution-suggestion.md`

**How to Use:** Create a `.github/ISSUE_TEMPLATE/` folder in your repo and place the issue template `.md` file inside.

```yaml
name: Contribution Suggestion
description: Suggest a new alias, feature, or improvement to the DV standardization tool
title: "[Suggestion]: "
labels: [enhancement]
assignees: ''

body:
  - type: textarea
    attributes:
      label: Summary of Suggestion
      description: Briefly describe the update you are proposing.
      placeholder: e.g., Add alias "time_spent" for "task_completion_time"
    validations:
      required: true

  - type: dropdown
    attributes:
      label: Type of Contribution
      options:
        - New DV alias
        - Dataset suggestion
        - Feature enhancement
        - LLM/semantic extension
        - UI improvement
    validations:
      required: true

  - type: input
    attributes:
      label: Related Publication or Dataset (optional)
      placeholder: DOI, GitHub repo, or dataset link
    validations:
      required: false
```

#### b. `.github/PULL_REQUEST_TEMPLATE.md`

**How to Use:** Place the `PULL_REQUEST_TEMPLATE.md` file directly under `.github/`.

```markdown
# Pull Request: Contribution to dv-standardization-tool

## Summary
Describe briefly what this pull request introduces or changes.

## Type of Contribution
- [ ] New DV alias or mapping
- [ ] Dataset example (raw or processed)
- [ ] Feature or functionality improvement
- [ ] Documentation update
- [ ] Other (please specify):

## Checklist
- [ ] Code/scripts follow repo conventions
- [ ] Changes are clearly explained and documented
- [ ] If applicable, updated `standard_dv_mapping.yaml`
- [ ] No sensitive data or personally identifiable information (PII) is included

## Additional Notes
(Optional) Add any context, references, or future follow-ups here.
```
