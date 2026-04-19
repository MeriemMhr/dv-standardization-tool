"""Streamlit UI for OpenDV-HCI standardization, catalog workflows, and analysis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.convert_dv import identify_unmapped_columns, standardize_columns
from ui.components.charts import (
    build_mapping_quality_chart,
    build_meta_analysis_chart,
    build_overlap_detail_chart,
    build_overlap_heatmap,
    build_presence_heatmap,
)
from ui.components.column_preview import show_column_comparison
from ui.components.download_button import render_table_download_buttons
from ui.components.uploader import list_excel_sheets, load_uploaded_table, upload_tabular_file

DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "standard_dv_mapping.yaml"
STREAMLIT_RUN_ROOT = REPO_ROOT / "data" / "processed" / "streamlit_runs"

st.set_page_config(page_title="OpenDV-HCI Tool", layout="wide")


@st.cache_data(show_spinner=False)
def _load_schema(schema_path: str) -> dict:
    with open(schema_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _inject_css() -> None:
    css_path = Path(__file__).resolve().parent / "assets" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _build_mapping(schema: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for dv in schema.get("dvs", []) or []:
        if not isinstance(dv, dict):
            continue
        canonical = dv.get("id")
        if not canonical:
            continue
        mapping[canonical] = canonical
        mapping[canonical.lower()] = canonical
        for alias in dv.get("aliases") or []:
            if not isinstance(alias, str):
                continue
            mapping[alias] = canonical
            mapping[alias.lower()] = canonical
    return mapping


def _default_output_dir(stem: str, suffix: str) -> str:
    STREAMLIT_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    return str((STREAMLIT_RUN_ROOT / f"{stem}_{suffix}").resolve())


def _save_uploaded_file(uploaded_file, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(uploaded_file.getvalue())
    return destination


def _load_catalog_outputs(output_dir: Path) -> dict[str, object]:
    analysis_dir = output_dir / "analysis"
    result: dict[str, object] = {
        "source_summary": pd.read_csv(output_dir / "catalog_source_summary.csv"),
        "analysis_summary": json.loads((analysis_dir / "analysis_summary.json").read_text(encoding="utf-8")),
        "overlap": pd.read_csv(analysis_dir / "dv_overlap_matrix.csv", index_col=0),
        "presence": pd.read_csv(analysis_dir / "dv_presence_matrix.csv", index_col=0),
        "overlap_details": pd.read_csv(analysis_dir / "dv_overlap_details.csv"),
        "meta": pd.read_csv(analysis_dir / "meta_analysis_summary.csv"),
        "harmonized": pd.read_csv(analysis_dir / "harmonized_dv_summary.csv"),
        "output_dir": output_dir,
    }
    composite_path = analysis_dir / "cross_study_composite_summary.csv"
    result["composite"] = pd.read_csv(composite_path) if composite_path.exists() else pd.DataFrame()
    return result


def _render_plotly_chart(builder, *args, **kwargs) -> None:
    try:
        figure = builder(*args, **kwargs)
    except ImportError as exc:
        st.info(str(exc))
        return
    if figure is None:
        return
    st.plotly_chart(figure, use_container_width=True)


def _render_single_dataset_tab() -> None:
    st.subheader("Single Dataset Standardization")
    st.caption("Upload one CSV/Excel file, inspect the mapping, and download cleaned outputs.")

    uploaded_file = upload_tabular_file(
        "Upload a CSV or Excel dataset",
        key="single_dataset_upload",
        help_text="For batch processing and meta-analysis, use the Catalog Workflow tab.",
    )
    if uploaded_file is None:
        return

    try:
        df_raw = load_uploaded_table(uploaded_file)
    except Exception as exc:
        st.error(f"Failed to load file: {exc}")
        return

    if df_raw.empty:
        st.warning("The uploaded file is empty or contains no data.")
        return

    schema = _load_schema(str(DEFAULT_SCHEMA_PATH))
    mapping = _build_mapping(schema)
    df_clean = standardize_columns(df_raw.copy(), mapping)

    unknown_columns = identify_unmapped_columns([str(column) for column in df_raw.columns], mapping)
    total_columns = len(df_raw.columns)
    mapped_columns = total_columns - len(unknown_columns)
    mapping_rate = (mapped_columns / total_columns) if total_columns else 0.0

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Mapped Columns", mapped_columns)
    metric_col2.metric("Unmapped Columns", len(unknown_columns))
    metric_col3.metric("Mapping Rate", f"{mapping_rate:.0%}")

    _render_plotly_chart(build_mapping_quality_chart, mapped_columns, len(unknown_columns))

    if unknown_columns:
        st.warning("Unmapped aliases detected: " + ", ".join(unknown_columns))

    show_column_comparison(df_raw, df_clean)

    raw_tab, standardized_tab = st.tabs(["Raw Data Preview", "Standardized Data Preview"])
    with raw_tab:
        st.dataframe(df_raw.head(50), use_container_width=True)
    with standardized_tab:
        st.dataframe(df_clean.head(50), use_container_width=True)

    st.subheader("Download")
    render_table_download_buttons(
        df_clean,
        file_stem=f"{Path(uploaded_file.name).stem}_standardized",
        key_prefix="single_dataset_download",
        csv_label="Download Standardized CSV",
        excel_label="Download Standardized Excel",
    )


def _render_catalog_workflow_tab() -> None:
    st.subheader("Catalog Workflow")
    st.caption(
        "Upload a catalog CSV/Excel with a URL or local-path column to run batch mapping "
        "and interactive cross-study analysis in one step."
    )

    try:
        from scripts.run_catalog_meta_analysis import build_sources_from_catalog, run_catalog_meta_analysis
    except ImportError as exc:
        st.error(
            "Catalog workflow dependencies are missing. Install with "
            "`pip install -r requirements-core.txt -r requirements-ui.txt`.\n\n"
            f"Import error: {exc}"
        )
        return

    uploaded_catalog = upload_tabular_file(
        "Upload a catalog CSV or Excel file",
        key="catalog_workflow_upload",
        help_text="Local paths in the catalog must be accessible from the machine running Streamlit.",
    )
    if uploaded_catalog is None:
        return

    sheet_names = list_excel_sheets(uploaded_catalog)
    selected_sheet: str | int = 0
    if sheet_names:
        selected_sheet = st.selectbox(
            "Worksheet",
            options=sheet_names,
            key="catalog_sheet_selector",
        )

    catalog_df = load_uploaded_table(uploaded_catalog, sheet_name=selected_sheet)
    st.write("Catalog Preview")
    st.dataframe(catalog_df.head(50), use_container_width=True)

    columns = [str(column) for column in catalog_df.columns]
    default_url_index = 0
    for idx, column in enumerate(columns):
        lowered = column.lower()
        if any(token in lowered for token in ("url", "location", "dataset")):
            default_url_index = idx
            break

    url_column = st.selectbox(
        "Dataset URL/path column",
        options=columns,
        index=default_url_index,
        key="catalog_url_column",
    )
    source_id_option = st.selectbox(
        "Source ID column",
        options=["(Auto)"] + columns,
        key="catalog_source_id_column",
    )
    source_type_option = st.selectbox(
        "Source type column",
        options=["(Auto)"] + columns,
        key="catalog_source_type_column",
    )
    context_columns = st.multiselect(
        "Context columns to fold into source notes",
        options=[column for column in columns if column not in {url_column}],
        key="catalog_context_columns",
    )

    default_output_dir = _default_output_dir(Path(uploaded_catalog.name).stem, "catalog")
    output_dir_text = st.text_input(
        "Output directory",
        value=default_output_dir,
        key="catalog_output_dir",
    )
    enable_llm = st.checkbox("Enable LLM alias deduction", value=True, key="catalog_enable_llm")
    preferred_models_text = st.text_input(
        "Preferred LLM models (optional, comma-separated)",
        value="",
        key="catalog_llm_models",
    )
    refresh_remote_cache = st.checkbox(
        "Refresh remote cache",
        value=False,
        key="catalog_refresh_cache",
    )
    debug_mappings = st.checkbox(
        "Write mapping debug artifacts",
        value=False,
        key="catalog_debug_mappings",
    )

    source_id_column = None if source_id_option == "(Auto)" else source_id_option
    source_type_column = None if source_type_option == "(Auto)" else source_type_option

    preview_sources_error = None
    preview_source_summary = None
    try:
        _, preview_source_summary = build_sources_from_catalog(
            catalog_df,
            url_column=url_column,
            source_id_column=source_id_column,
            source_type_column=source_type_column,
            context_columns=context_columns,
        )
    except Exception as exc:  # noqa: BLE001
        preview_sources_error = str(exc)

    st.write("Resolved Source Preview")
    if preview_sources_error:
        st.error(preview_sources_error)
    elif preview_source_summary is not None:
        st.dataframe(preview_source_summary, use_container_width=True)

    run_button = st.button("Run Catalog Mapping + Analysis", type="primary", key="catalog_run_button")
    if run_button and not preview_sources_error:
        output_dir = Path(output_dir_text).expanduser()
        saved_catalog_path = output_dir / uploaded_catalog.name
        preferred_models = [item.strip() for item in preferred_models_text.split(",") if item.strip()] or None

        with st.spinner("Running batch standardization and cross-study analysis..."):
            _save_uploaded_file(uploaded_catalog, saved_catalog_path)
            summary = run_catalog_meta_analysis(
                catalog_path=saved_catalog_path,
                url_column=url_column,
                output_dir=output_dir,
                sheet_name=selected_sheet,
                source_id_column=source_id_column,
                source_type_column=source_type_column,
                context_columns=context_columns,
                llm_deduction_enabled=enable_llm,
                preferred_models=preferred_models,
                refresh_remote_cache=refresh_remote_cache,
                debug_mappings=debug_mappings,
            )
        st.session_state["catalog_analysis_output_dir"] = str(output_dir)
        st.session_state["catalog_analysis_summary"] = summary
        st.success(f"Workflow completed. Artifacts saved to {output_dir}")

    output_dir_value = st.session_state.get("catalog_analysis_output_dir")
    if not output_dir_value:
        return

    output_dir = Path(str(output_dir_value))
    if not output_dir.exists():
        st.warning("The last catalog output directory no longer exists.")
        return

    results = _load_catalog_outputs(output_dir)
    summary = results["analysis_summary"]
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Unique Sources", int(summary["n_unique_sources"]))
    metric_col2.metric("Loaded Studies", int(summary["n_loaded_studies"]))
    metric_col3.metric("Meta-analysis Rows", int(summary["meta_analysis_row_count"]))
    avg_jaccard = summary["average_pairwise_jaccard"]
    metric_col4.metric(
        "Avg Pairwise Overlap",
        "n/a" if avg_jaccard is None else f"{float(avg_jaccard):.2f}",
    )

    overview_tab, overlap_tab, meta_tab, artifacts_tab = st.tabs(
        ["Overview", "Overlap", "Meta-analysis", "Artifacts"]
    )

    with overview_tab:
        st.write("Source Summary")
        st.dataframe(results["source_summary"], use_container_width=True)
        st.write("Harmonized DV Summary")
        st.dataframe(results["harmonized"].head(100), use_container_width=True)
        if not results["composite"].empty:
            st.write("Composite Index Summary")
            st.dataframe(results["composite"], use_container_width=True)

    with overlap_tab:
        left, right = st.columns(2)
        with left:
            _render_plotly_chart(build_overlap_heatmap, results["overlap"])
        with right:
            _render_plotly_chart(build_presence_heatmap, results["presence"])
        _render_plotly_chart(build_overlap_detail_chart, results["overlap_details"])
        st.dataframe(results["overlap_details"], use_container_width=True)

    with meta_tab:
        _render_plotly_chart(build_meta_analysis_chart, results["meta"])
        if results["meta"].empty:
            st.info("No random-effects rows were produced for this run.")
        else:
            st.dataframe(results["meta"], use_container_width=True)

    with artifacts_tab:
        st.code(str(output_dir))
        st.json(summary)
        render_table_download_buttons(
            results["meta"],
            file_stem="meta_analysis_summary",
            key_prefix="catalog_meta_download",
            csv_label="Download Meta-analysis CSV",
            excel_label="Download Meta-analysis Excel",
        )
        render_table_download_buttons(
            results["overlap_details"],
            file_stem="dv_overlap_details",
            key_prefix="catalog_overlap_download",
            csv_label="Download Overlap Details CSV",
            excel_label="Download Overlap Details Excel",
        )


_inject_css()

st.title("OpenDV-HCI")
st.caption(
    "Standardize dependent variables, run catalog-based study ingestion, and explore overlap/meta-analysis "
    "results without leaving the same UI."
)

single_tab, catalog_tab = st.tabs(["Single Dataset", "Catalog Workflow"])
with single_tab:
    _render_single_dataset_tab()
with catalog_tab:
    _render_catalog_workflow_tab()
