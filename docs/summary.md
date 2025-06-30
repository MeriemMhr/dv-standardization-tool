### Project Documentation Overview

The `docs/` directory serves as the central hub for all internal documentation related to the project. It provides clear guidance on directory structure, development rationale, future plans, and key references. This structure is designed to support collaboration, reproducibility, and ongoing iteration throughout the research and prototyping phases.

| Filename                   | Description                                                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `overview.md`              | Concise research context, goals, and intended impact—written as an academic abstract + narrative overview.                                  |
| `architecture.md`          | How the scripts, schemas, UI, and datasets work together—include diagrams or pseudo-architecture where helpful.                             |
| `schema_design.md`         | Design decisions, aliasing conventions, YAML hierarchy, versioning strategies, and semantic considerations.                                 |
| `dataset_guidelines.md`    | Dataset formatting rules, common pitfalls, anonymization practices, and mapping compatibility.                                              |
| `usage_workflows.md`       | End-to-end walkthroughs (e.g., raw CSV → standardized CSV), with references to scripts, schema usage, and notebooks.                        |
| `future_plans.md`          | Your evolving roadmap—LLM integration, fuzzy matching improvements, schema auto-inference, Streamlit UX upgrades, export enhancements, etc. |
| `directory_map.md`         | Bullet-style or tree-style map of your repo’s folders, plus what belongs where and why.                                                     |
| `troubleshooting_index.md` | A guide pointing to contents of `troubleshooting/`, linking log types to causes and solutions.                                              |
| `changelog.md`             | Human-readable evolution history of the project and major milestones. (Optional complement to `schema_changelog.yaml`.)                     |
