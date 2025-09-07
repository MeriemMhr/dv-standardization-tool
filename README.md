## OpenDV-HCI: A Toolkit for Reproducible Mapping and Reporting of Dependent Variables
**`Standardizing Outcome Measures in Empirical HCI Research Through Schema-Driven Conversion and Open Data Harmonization`**

* **Postgraduate Contributor:** [Meriem Mehri](https://www.linkedin.com/in/meriem-mehri/), [UCL Engineering - Computer Science Department](https://www.ucl.ac.uk/engineering/computer-science)
* **Academic Supervisor**: [Mark Colley](https://m-colley.github.io/), [UCL Interaction Centre (UCLIC)](https://www.ucl.ac.uk/uclic)
* **Programme**: Artificial Intelligence for Sustainable Development MSc

<img src="standardization_flowchart.png" alt="Column standardization pipeline" width="750"/>

> This diagram outlines the full standardization and naming pipeline — from raw dataset upload and inference to column matching, canonicalization, and final export. It represents the conceptual framework guiding the core logic and schema design of the research inquiry.
---

## Overview
This repository accompanies the MSc research project titled *"Standardizing Reporting of Dependent Variables in HCI Research: A Naming Scheme and Conversion Tool for Open Data"* (Project Code: P09). The project addresses the pressing challenge of methodological fragmentation and inconsistent naming conventions of dependent variables (DVs) across empirical Human-Computer Interaction (HCI) research.  

Drawing on systematic evidence from [CHI](https://chi2025.acm.org/), [CHI PLAY](https://chiplay.acm.org/2025/), [AutoUI](https://www.auto-ui.org/25/), and other top-tier venues, the project proposes both a **flexible naming scheme** and a **conversion tool** to improve transparency, interoperability, and comparability across open HCI datasets.  

---

## Motivation & Problem Statement
While the HCI community has increasingly embraced open science practices, critical gaps remain in the standardization of outcome variable reporting. Studies frequently use inconsistent labels for conceptually similar constructs (e.g., `taskTime`, `completion_time`, `time_to_complete_task`), hindering:

- Cross-study synthesis and meta-analysis  
- Dataset reuse and integration  
- Empirical reproducibility  
- Compliance with [FAIR data principles](https://www.go-fair.org/fair-principles/)

Despite ongoing advocacy for open methods (Koelle et al., 2024; Goodman et al., 2022), raw data sharing and construct standardization remain underdeveloped in practice. This tool directly addresses those limitations by offering a practical, evidence-driven solution.

---

## Research Objectives
1. Conduct a structured literature review to assess DV reporting inconsistencies and transparency practices in empirical HCI.
2. Develop a DV naming scheme grounded in open science principles and informed by best practices across HCI, psychology, and reproducibility science.
3. Implement a Python-based conversion tool to map inconsistent DV labels to standardized terms.
4. Validate the tool using open datasets from leading conferences and repositories (e.g., [ROADS-CHI25](https://doi.org/10.1145/3640792.3675730)).
5. Advance interoperability and responsible research practices in line with SDG 12 (Responsible Consumption and Production).

---

## Repository Structure & Rationale
This repository functions as a testbed to evaluate the viability of a canonical naming scheme for dependent variables (DVs) in HCI research and to empirically ground the hypothesis that harmonizing DV nomenclature can significantly enhance dataset interoperability, reuse, and reproducibility. Each folder and script within the repository was carefully aligned with dissertation components to ensure traceability across research stages. The `schemas/` directory houses the naming scheme that operationalizes the standardization logic. The `scripts/` folder contains the conversion tool’s core implementation, demonstrating how real datasets can be mapped using this schema. The notebooks/ directory supports schema ideation (schema_builder.ipynb), validation testing (prototype_notebook.ipynb), visual exploration (visual_validation.ipynb), and forward-looking LLM prototyping (llm_inference_prototype.ipynb). Raw input data and standardized outputs are stored respectively in `data/raw/` and `data/processed/`, thereby offering before/after evidence for tool performance and transformation fidelity. Additional design rationale, transparency strategies, and schema expansion plans are documented in `docs/`, reinforcing the project’s alignment with open science principles. Altogether, the repository serves not only as a demonstration artifact but also as an empirical anchor for validating the dissertation’s core research claims.

```bash
dv-standardization-tool/
├── data/
│   ├── raw/                      # Original datasets (e.g., CHI open datasets)
│   └── processed/                # Datasets after DV standardization
│
├── schemas/
│   ├── standard_dv_mapping.yaml         # Canonical DV naming scheme
│   ├── schema_meta.yaml                 # Schema metadata (versioning, authorship)
│   ├── schema_validation_rules.yaml     # Optional constraint rules
│   ├── example_alias_submissions.yaml   # Sample community submissions
│   └── schema_changelog.yaml            # Manual schema evolution tracking
│
├── scripts/
│   ├── convert_dv.py            # Core logic for DV transformation
│   ├── schema_utils.py          # Flattening, validation, and schema helpers
│   ├── visual_helpers.py        # Comparison visualizations
│   ├── validate_schema.py       # Schema sanity check
│   └── llm_utils.py             # Optional LLM inference logic
│
├── notebooks/
│   ├── prototype_notebook.ipynb         # Main schema validation/testing
│   ├── schema_builder.ipynb             # Manual YAML construction notebook
│   ├── visual_validation.ipynb          # Schema alignment visualization
│   └── llm_inference_prototype.ipynb    # Optional LLM-based prototype
│
├── ui/
│   ├── app.py                   # Streamlit app entry point
│   ├── uploader.py              # Upload logic
│   ├── column_preview.py        # Column-level feedback
│   ├── download_button.py       # Download-ready output
│   ├── assets/
│   │   └── style.css            # Minimal styling
│   └── components/              # Optional modular UI elements
│
├── .github/
│   └── ISSUE_TEMPLATE/
│       └── contribution-suggestion.md
│   └── PULL_REQUEST_TEMPLATE.md
│
├── docs/
│   ├── overview.md
│   ├── architecture.md
│   ├── usage_workflows.md
│   ├── schema_design.md
│   ├── dataset_guidelines.md
│   ├── future_plans.md
│   ├── directory_map.md
│   ├── troubleshooting_index.md
│   └── changelog.md
│
├── troubleshooting/
│   ├── known_issues.md
│   ├── schema_mismatches.md
│   ├── notebook_dependency_notes.md
│   ├── log_2024-07-01_streamlit_example.txt
│   ├── llm_prompt_failures.md
│   ├── trace_convert_dv.txt
│   ├── notebook_kernel_error.txt
│   └── broken_schema_preview_example.png
│
├── LICENSE
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Tool Description
The core functionality is a **conversion pipeline** for standardizing column names in `.csv` files using a YAML-based DV mapping schema. The tool allows researchers to rapidly harmonize datasets, reducing manual effort and promoting reproducibility.

```bash
python scripts/convert_dv.py \
  --input data/raw/sample.csv \
  --output data/processed/standardized.csv
```

Example schema (`schemas/standard_dv_mapping.yaml`):

```yaml
task_completion_time:
  - taskTime
  - completionTime
  - time_to_complete_task

user_satisfaction:
  - SUS
  - satisfaction_score
  - subjective_rating
```
> For practical workflows and applied examples, refer to [`docs/usage_workflows.md`](docs/usage_workflows.md).

---
## Capabilities

- Schema-driven conversion of raw DV columns into standardized formats
- YAML-based mapping logic for extensibility and transparency
- Visualization of schema coverage and alignment across datasets
- Optional LLM-based inference for alias suggestion (prototype stage)
- Reproducible prototyping via Jupyter notebooks
- Optional lightweight UI layer for upload-to-export interaction

---
## Methodology
This project followed a rigorous structured literature review methodology defined under the COMP0190 module at UCL. Key steps included:

* Review of >100 papers across CHI (2015-2025), CHI PLAY, AutoUI, and IMWUT, etc. — using PRISMA principles.
* Thematic coding of DV terminology, transparency practices, and naming patterns.
* Development of schema based on recurring inconsistencies in the literature (cf. Aeschbach et al., 2021; Putze et al., 2022).
* Evaluation through a pilot case study using the ROADS dataset (Colley et al., 2024).

> The literature review underpinning this tool was conducted using **Sysrev** ([https://sysrev.com](https://sysrev.com)), a collaborative web-based platform designed for systematic evidence synthesis. Sysrev was selected for its ability to support structured review workflows, including multi-level screening, custom tag definitions, and collaborative annotation. A bespoke review protocol was implemented to identify empirical HCI papers reporting dependent variables, with a focus on CHI, CHI PLAY, AutoUI, and related venues between 2017 and 2024. Custom tagging schemes were developed to encode variable names, study domains, and transparency indicators. This approach enabled rigorous extraction and cross-referencing of DV naming inconsistencies, which directly informed the construction of the canonical naming schema embedded in this tool. The use of Sysrev also ensured traceability of decisions, reproducibility of screening logic, and exportability of encoded metadata into structured formats for further analysis.

---

## Anticipated Impact
This work contributes toward:

* Enhanced reproducibility through improved metadata quality and DV clarity.
* Cross-study comparability of HCI empirical results.
* Reduced duplication of effort through interoperable dataset design.
* Open science alignment, encouraging responsible research practices and standard reuse.

*It also serves as a foundation for integrating HCI with broader open metadata infrastructures, such as FAIRsharing and OSF.*

---

## Evaluation Strategy
Tool effectiveness will be assessed through:

* Pre/post comparison of dataset clarity and structure.
* Quantitative match rates of non-standard to standardized variables.
* Qualitative feedback from HCI researchers on schema usability.
* Interoperability assessment using FAIR principles (Wilkinson et al., 2016).

---

## Regulatory & Ethical Considerations
Aligned with the UK AI regulatory framework, the tool is classified as a **"supporting system"** for research infrastructure. Ethical compliance is ensured by:

* Operating exclusively on anonymized, public datasets
* Providing open-source documentation and logging all schema changes
* Supporting community participation in schema revision via GitHub pull requests

---

## Future Work
* Extend the mapping schema to cover qualitative and mixed-method dependent variables, accounting for construct diversity in mixed designs.
* Integrate fuzzy matching capabilities (e.g., via `rapidfuzz`) to enhance robustness against minor lexical variations and human-annotated inconsistencies.
* Build a lightweight [Streamlit](https://streamlit.io) user interface to enable upload-based DV harmonization for non-technical users and HCI practitioners.
* Investigate interoperability with semantic frameworks and metadata standards (e.g., CEDAR, BioPortal) to facilitate alignment with existing ontology-driven research infrastructures.
* Explore the integration of large language models (LLMs) for context-aware variable suggestion, auto-tagging, and disambiguation. This would allow the tool to provide intelligent recommendations for ambiguous or undocumented variable names based on surrounding metadata, potentially accelerating schema expansion and dataset onboarding.
* Incorporate visual analytics to compare pre- and post-standardization states, highlight variable overlaps, and provide interpretable mappings — useful for validation, stakeholder engagement, and pedagogical use.
* Pilot the tool across a broader range of HCI datasets and venues, and refine it into a reusable, community-adoptable research artifact supporting long-term reproducibility and responsible data practices.
---

## References

*The following represent a selected subset of key academic references that informed the design rationale, methodological approach, and conceptual framing of this project. While not exhaustive, these citations reflect foundational contributions to discussions on reproducibility, open science, and metadata standardization in empirical HCI research:*

* **Goodman, N., & Koelle, M. (2024).** *Changing Lanes Toward Open Science: Envisioning an Open, Transparent Future for Empirical HCI Research*. In *Proceedings of the ACM on Human-Computer Interaction (PACMHCI)*, CHI 2024. [https://doi.org/10.1145/3640792.3675730)]([https://doi.org/10.1145/XXXXXX](https://dl.acm.org/doi/10.1145/3640792.3675730)
  
* **Wilkinson, M. D., Dumontier, M., Aalbersberg, I. J., et al. (2016).** The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data*, 3, 160018. [https://doi.org/10.1038/sdata.2016.18](https://doi.org/10.1038/sdata.2016.18)

---

## Citation
If you use this repository or the accompanying tool, please cite:

> Mehri, M. (2025). *Breaking data silos in HCI: A standardized framework and open-source tool for FAIR, reproducible, and cumulative research (MSc dissertation, University College London)*. UCL Interaction Centre. [GitHub Repository](https://github.com/MeriemMhr/dv-standardization-tool)


#### BibTeX

```bibtex
@mastersthesis{mehri2025dvs,
  author       = {Meriem Mehri},
  title        = {Breaking Data Silos in HCI: A Standardized Framework and Open-Source Tool for FAIR, Reproducible, and Cumulative Research},
  school       = {University College London (UCL) Interaction Centre},
  year         = {2025},
  type         = {Master's Dissertation},
  url          = {https://ucl.ac.uk/interaction-centre},
}
```

## Contact Details

* **Author**: Meriem Mehri
* **Supervisor**: Mark Colley
* **Institution**: UCL Interaction Centre (UCLIC), University College London
* **Emails**: [meriem.mehri.24@ucl.ac.uk](mailto:meriem.mehri.24@ucl.ac.uk) ; [m.colley@ucl.ac.uk](mailto:m.colley@ucl.ac.uk)
