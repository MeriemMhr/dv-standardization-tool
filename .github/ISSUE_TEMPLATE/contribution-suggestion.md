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
