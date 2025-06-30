# Future Plans & Integration Roadmap

This document outlines the forward-looking roadmap for enhancing the DV Standardization Tool. These potential improvements aim to broaden the tool's applicability, improve usability, and align with best practices in responsible HCI research, reproducibility, and open science infrastructure.

## LLM Integration

One promising direction involves incorporating large language models (LLMs) to support intelligent alias detection and semantic inference. Specifically, LLMs can be used to auto-suggest appropriate mappings for ambiguous or previously unseen dependent variable (DV) column names. This may be particularly useful when working with large or multilingual datasets, or when encountering domain-specific constructs not yet represented in the canonical schema. Initial utilities for LLM prompting are scaffolded in `scripts/llm_utils.py`. Additionally, the use of semantic embeddings could allow for unsupervised clustering of DV names, facilitating schema refinement and cross-study harmonization at scale.

## Enhanced Visualization

Improved visualization capabilities are envisioned to assist with both development and interpretation of the tool's output. In particular, we plan to expand the column comparison visualizations implemented in `scripts/visual_helpers.py` to support more flexible plotting, heatmaps, and schema overlay views. These visualizations would be instrumental in validating fuzzy matches and in conveying the standardization impact to users and reviewers. A secondary goal is to explore visual schema mapping interfaces that dynamically reflect the transformation from raw to standardized formats.

## UI Roadmap

While the current project is backend-focused, an optional frontend layer is being prototyped using Streamlit. The goal is to offer a lightweight, interactive dashboard (`ui/app.py`) for research users who prefer visual or no-code interfaces. This includes support for drag-and-drop dataset uploads, downloadable output previews, and configuration of schema mappings. Styling is handled via a minimal CSS layer (`ui/assets/style.css`), and future iterations will explore themes such as dark mode. These interface features, while not core to the thesis, serve to demonstrate the extensibility and adoption potential of the tool in open research environments.
