# DV Schema Design

## Why YAML?
YAML was chosen for its:
- Human readability
- Nested hierarchy support
- Compatibility with version control systems

## Naming Convention Principles
Drawing from inconsistencies highlighted in CHI, AutomotiveUI, and CHI PLAY literature:
- Use **lower_snake_case** for all variable names
- Include **construct**, **metric**, and **unit** fields
- Support **aliases** for mapping legacy names

## Example YAML Structure

```yaml
dependent_variable:
  name: task_completion_time
  construct: efficiency
  metric: duration
  unit: seconds
  aliases:
    - time_taken
    - completion_time
    - total_time
