#!/usr/bin/env python3
"""Catalog-driven workflow for URL-based batch standardization and meta-analysis."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analyses.multi_study_analysis import (
    build_composite_index,
    compute_dv_presence_matrix,
    compute_overlap,
    compute_overlap_details,
    compute_standardized_effects,
    harmonized_summary,
    load_mapping_provenance,
    load_studies,
    meta_analysis_summary,
    save_composite_plot,
    save_plots,
)
from scripts.run_batch_standardization import run_batch

DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "standard_dv_mapping.yaml"
REMOTE_DATASET_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xls", ".pkl", ".pickle", ".zip", ".yaml", ".yml"}
WEB_DATASET_HOSTS = {
    "data.4tu.nl",
    "www.data.4tu.nl",
    "ieee-dataport.org",
    "www.ieee-dataport.org",
    "wjx.cn",
    "www.wjx.cn",
}
LIST_LIKE_FIELDS = {
    "include_globs",
    "exclude_globs",
    "llm_models",
    "publication_doi",
    "publication_pdf_url",
    "llm_context",
    "publication_context",
}
SCALAR_FIELDS = {"ref", "mapping_path"}
BOOLEAN_FIELDS = {"use_llm_deduction", "extract_archives"}
INTEGER_FIELDS = {"archive_max_depth"}


def _read_catalog_table(catalog_path: Path, sheet_name: str | int = 0) -> pd.DataFrame:
    suffix = catalog_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(catalog_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(catalog_path, sheet_name=sheet_name)
    raise ValueError(
        f"Unsupported catalog format '{suffix or 'no extension'}'. Use .csv, .xlsx, or .xls."
    )


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _normalize_string(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip()


def _parse_list_cell(value: Any) -> list[str]:
    if _is_missing(value):
        return []
    if isinstance(value, (list, tuple, set)):
        return [text for text in (_normalize_string(item) for item in value) if text]

    text = _normalize_string(value)
    if not text:
        return []

    try:
        parsed = yaml.safe_load(text)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        return [item for item in (_normalize_string(entry) for entry in parsed) if item]

    if any(separator in text for separator in ("\n", ";", "|")):
        return [item.strip() for item in re.split(r"[;\n|]+", text) if item.strip()]
    if "," in text and "http://" not in text and "https://" not in text:
        return [item.strip() for item in text.split(",") if item.strip()]
    return [text]


def _parse_bool_cell(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in {0, 1}:
            return bool(value)
    text = _normalize_string(value).lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _parse_int_cell(value: Any) -> int | None:
    if _is_missing(value):
        return None
    if isinstance(value, int):
        return value
    text = _normalize_string(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _infer_source_type(location: str) -> str:
    parsed = urlparse(location)
    if parsed.scheme in {"http", "https"}:
        host = parsed.netloc.lower()
        if "github.com" in host:
            return "github_repo"
        if "osf.io" in host:
            return "osf_project"
        if host in WEB_DATASET_HOSTS or Path(parsed.path).suffix.lower() in REMOTE_DATASET_SUFFIXES:
            return "web_dataset"
    if Path(location).expanduser().exists():
        return "local_path"
    raise ValueError(
        f"Could not infer source_type for '{location}'. Provide a source_type column or use a GitHub/OSF/web dataset/local path."
    )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug or "source"


def _make_unique_source_id(base: str, seen_ids: set[str]) -> str:
    candidate = _slugify(base)
    if candidate not in seen_ids:
        seen_ids.add(candidate)
        return candidate

    index = 2
    while f"{candidate}_{index}" in seen_ids:
        index += 1
    unique = f"{candidate}_{index}"
    seen_ids.add(unique)
    return unique


def _derive_source_id(location: str, seen_ids: set[str]) -> str:
    parsed = urlparse(location)
    if parsed.scheme in {"http", "https"}:
        host = parsed.netloc.lower()
        parts = [part for part in parsed.path.split("/") if part]
        if "github.com" in host and len(parts) >= 2:
            return _make_unique_source_id(f"{parts[0]}_{parts[1]}", seen_ids)
        if "osf.io" in host and parts:
            return _make_unique_source_id(f"osf_{parts[0]}", seen_ids)
        tail = parts[-1] if parts else host.replace(".", "_")
        return _make_unique_source_id(f"{host.replace('.', '_')}_{tail}", seen_ids)

    local_path = Path(location)
    base = local_path.stem or local_path.name or "source"
    return _make_unique_source_id(base, seen_ids)


def _collapse_scalar(values: list[Any], field_name: str, location: str) -> str | None:
    cleaned = [_normalize_string(value) for value in values if _normalize_string(value)]
    unique = list(dict.fromkeys(cleaned))
    if not unique:
        return None
    if len(unique) > 1:
        raise ValueError(
            f"Conflicting '{field_name}' values for location '{location}': {unique}"
        )
    return unique[0]


def _collapse_boolean(values: list[Any], field_name: str, location: str) -> bool | None:
    cleaned = [parsed for parsed in (_parse_bool_cell(value) for value in values) if parsed is not None]
    unique = list(dict.fromkeys(cleaned))
    if not unique:
        return None
    if len(unique) > 1:
        raise ValueError(
            f"Conflicting '{field_name}' values for location '{location}': {unique}"
        )
    return unique[0]


def _collapse_integer(values: list[Any], field_name: str, location: str) -> int | None:
    cleaned = [parsed for parsed in (_parse_int_cell(value) for value in values) if parsed is not None]
    unique = list(dict.fromkeys(cleaned))
    if not unique:
        return None
    if len(unique) > 1:
        raise ValueError(
            f"Conflicting '{field_name}' values for location '{location}': {unique}"
        )
    return unique[0]


def _build_context_notes(group: pd.DataFrame, context_columns: list[str]) -> list[str]:
    notes: list[str] = []
    for _, row in group.iterrows():
        parts = []
        for column in context_columns:
            if column not in group.columns:
                continue
            value = _normalize_string(row.get(column))
            if value:
                parts.append(f"{column}={value}")
        if parts:
            notes.append("Catalog row context: " + " | ".join(parts))
    return list(dict.fromkeys(notes))


def build_sources_from_catalog(
    catalog_df: pd.DataFrame,
    url_column: str,
    source_id_column: str | None = None,
    source_type_column: str | None = None,
    context_columns: list[str] | None = None,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    if url_column not in catalog_df.columns:
        raise ValueError(f"Column '{url_column}' was not found in the catalog.")

    normalized_locations = [_normalize_string(value) for value in catalog_df[url_column]]
    if not any(normalized_locations):
        raise ValueError(f"Column '{url_column}' does not contain any non-empty locations.")

    working_df = catalog_df.copy()
    working_df["__catalog_location__"] = normalized_locations
    working_df = working_df[working_df["__catalog_location__"] != ""].copy()

    ordered_locations = list(dict.fromkeys(working_df["__catalog_location__"].tolist()))
    seen_source_ids: set[str] = set()
    sources: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    context_columns = context_columns or []

    for location in ordered_locations:
        group = working_df[working_df["__catalog_location__"] == location].copy()
        explicit_source_id = (
            _collapse_scalar(group[source_id_column].tolist(), source_id_column, location)
            if source_id_column and source_id_column in group.columns
            else None
        )
        source_id = (
            _make_unique_source_id(explicit_source_id, seen_source_ids)
            if explicit_source_id
            else _derive_source_id(location, seen_source_ids)
        )

        explicit_source_type = (
            _collapse_scalar(group[source_type_column].tolist(), source_type_column, location)
            if source_type_column and source_type_column in group.columns
            else None
        )
        source_type = explicit_source_type or _infer_source_type(location)

        source_entry: dict[str, Any] = {
            "source_id": source_id,
            "source_type": source_type,
            "location": location,
        }

        for field_name in sorted(LIST_LIKE_FIELDS):
            if field_name not in group.columns:
                continue
            values: list[str] = []
            for value in group[field_name].tolist():
                values.extend(_parse_list_cell(value))
            if values:
                source_entry[field_name] = list(dict.fromkeys(values))

        context_notes = _build_context_notes(group, context_columns)
        if context_notes:
            merged_context = list(source_entry.get("llm_context", []))
            merged_context.extend(context_notes)
            source_entry["llm_context"] = list(dict.fromkeys(merged_context))

        for field_name in sorted(SCALAR_FIELDS):
            if field_name not in group.columns:
                continue
            value = _collapse_scalar(group[field_name].tolist(), field_name, location)
            if value is not None:
                source_entry[field_name] = value

        for field_name in sorted(BOOLEAN_FIELDS):
            if field_name not in group.columns:
                continue
            value = _collapse_boolean(group[field_name].tolist(), field_name, location)
            if value is not None:
                source_entry[field_name] = value

        for field_name in sorted(INTEGER_FIELDS):
            if field_name not in group.columns:
                continue
            value = _collapse_integer(group[field_name].tolist(), field_name, location)
            if value is not None:
                source_entry[field_name] = value

        sources.append(source_entry)
        source_rows.append(
            {
                "source_id": source_id,
                "source_type": source_type,
                "location": location,
                "catalog_row_count": int(len(group)),
            }
        )

    return sources, pd.DataFrame(source_rows)


def run_catalog_meta_analysis(
    catalog_path: str | Path,
    url_column: str,
    output_dir: str | Path,
    sheet_name: str | int = 0,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
    source_id_column: str | None = None,
    source_type_column: str | None = None,
    context_columns: list[str] | None = None,
    llm_deduction_enabled: bool = True,
    cache_dir: str | Path | None = None,
    refresh_remote_cache: bool = False,
    preferred_models: list[str] | None = None,
    debug_mappings: bool = False,
) -> dict[str, Any]:
    catalog_path = Path(catalog_path)
    output_dir = Path(output_dir)
    schema_path = Path(schema_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog_df = _read_catalog_table(catalog_path, sheet_name=sheet_name)
    sources, source_summary = build_sources_from_catalog(
        catalog_df,
        url_column=url_column,
        source_id_column=source_id_column,
        source_type_column=source_type_column,
        context_columns=context_columns,
    )

    manifest_path = output_dir / "generated_sources_manifest.yaml"
    source_summary_path = output_dir / "catalog_source_summary.csv"
    manifest_path.write_text(
        yaml.safe_dump({"sources": sources}, sort_keys=False),
        encoding="utf-8",
    )

    batch_summary = run_batch(
        manifest_path=manifest_path,
        output_dir=output_dir,
        schema_path=schema_path,
        llm_deduction_enabled=llm_deduction_enabled,
        cache_root=Path(cache_dir) if cache_dir else None,
        refresh_remote_cache=refresh_remote_cache,
        preferred_models=preferred_models,
        debug_mappings=debug_mappings,
    )

    batch_results = pd.DataFrame(batch_summary.get("results", []))
    if not batch_results.empty:
        summary_columns = [
            "source_id",
            "status",
            "message",
            "discovered_files",
            "processed_files",
            "failed_files",
        ]
        available_columns = [column for column in summary_columns if column in batch_results.columns]
        source_summary = source_summary.merge(
            batch_results[available_columns].rename(
                columns={
                    "status": "batch_status",
                    "message": "batch_message",
                }
            ),
            on="source_id",
            how="left",
        )
    source_summary.to_csv(source_summary_path, index=False)

    standardized_root = output_dir / "standardized"
    analysis_dir = output_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    try:
        studies = load_studies(standardized_root)
    except FileNotFoundError as exc:
        analysis_summary = {
            "catalog_path": str(catalog_path),
            "url_column": url_column,
            "n_catalog_rows": int(len(catalog_df)),
            "n_unique_sources": int(len(sources)),
            "n_loaded_studies": 0,
            "average_pairwise_jaccard": None,
            "meta_analysis_row_count": 0,
            "overlap_pair_count": 0,
            "composite_index_written": False,
            "batch_run_summary": batch_summary,
            "source_status_counts": (
                batch_results["status"].value_counts(dropna=False).to_dict()
                if "status" in batch_results.columns
                else {}
            ),
            "analysis_skipped_reason": str(exc),
        }
        (analysis_dir / "analysis_summary.json").write_text(
            json.dumps(analysis_summary, indent=2),
            encoding="utf-8",
        )
        return analysis_summary

    overlap = compute_overlap(studies)
    presence = compute_dv_presence_matrix(studies)
    overlap_details = compute_overlap_details(studies)
    mapping_provenance = load_mapping_provenance(output_dir / "meta_view.csv")
    summary = harmonized_summary(studies, mapping_provenance=mapping_provenance)
    meta_summary = meta_analysis_summary(summary, total_studies=len(studies))

    overlap.to_csv(analysis_dir / "dv_overlap_matrix.csv")
    presence.to_csv(analysis_dir / "dv_presence_matrix.csv")
    overlap_details.to_csv(analysis_dir / "dv_overlap_details.csv", index=False)
    summary.to_csv(analysis_dir / "harmonized_dv_summary.csv", index=False)
    meta_summary.to_csv(analysis_dir / "meta_analysis_summary.csv", index=False)
    save_plots(overlap, summary, analysis_dir)

    # Sensitivity companion: drop LLM-deduced rows and re-pool.  No-op when
    # provenance is unavailable; always safe to write so downstream consumers
    # can compare pooled estimates against a provenance-filtered reference.
    summary_clean = summary[summary["mapping_source"] != "llm_deduced"].copy()
    if len(summary_clean) < len(summary):
        meta_clean = meta_analysis_summary(
            summary_clean,
            total_studies=len(studies),
        )
        meta_clean.to_csv(
            analysis_dir / "meta_analysis_summary_llm_excluded.csv",
            index=False,
        )
        effects_clean = compute_standardized_effects(summary_clean)
        if not effects_clean.empty:
            effects_clean.to_csv(
                analysis_dir / "study_vs_pool_standardized_deviation_llm_excluded.csv",
                index=False,
            )

    composite_written = False
    try:
        composite = build_composite_index(studies)
        composite.to_csv(analysis_dir / "cross_study_composite_summary.csv", index=False)
        save_composite_plot(studies, analysis_dir)
        composite_written = True
    except ValueError:
        composite = pd.DataFrame()

    average_pairwise_jaccard = (
        float(overlap_details["jaccard_overlap"].mean())
        if not overlap_details.empty
        else None
    )
    analysis_summary = {
        "catalog_path": str(catalog_path),
        "url_column": url_column,
        "n_catalog_rows": int(len(catalog_df)),
        "n_unique_sources": int(len(sources)),
        "n_loaded_studies": int(len(studies)),
        "average_pairwise_jaccard": average_pairwise_jaccard,
        "meta_analysis_row_count": int(len(meta_summary)),
        "overlap_pair_count": int(len(overlap_details)),
        "composite_index_written": composite_written,
        "batch_run_summary": batch_summary,
        "source_status_counts": (
            batch_results["status"].value_counts(dropna=False).to_dict()
            if "status" in batch_results.columns
            else {}
        ),
    }
    (analysis_dir / "analysis_summary.json").write_text(
        json.dumps(analysis_summary, indent=2),
        encoding="utf-8",
    )
    return analysis_summary


def _coerce_sheet_name(value: str) -> str | int:
    text = value.strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    return text


def _parse_context_columns(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use a catalog CSV/Excel URL column to run mapping and cross-study meta-analysis."
    )
    parser.add_argument("--catalog", required=True, help="Catalog CSV/Excel file.")
    parser.add_argument("--url-column", required=True, help="Column containing dataset URLs or local paths.")
    parser.add_argument("--output-dir", required=True, help="Output directory for batch and analysis artifacts.")
    parser.add_argument("--sheet-name", default="0", help="Excel sheet name or index (default: 0).")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="DV schema YAML path.")
    parser.add_argument("--source-id-column", default=None, help="Optional column to use for source_id.")
    parser.add_argument("--source-type-column", default=None, help="Optional column to use for source_type.")
    parser.add_argument(
        "--context-columns",
        default=None,
        help="Optional comma-separated catalog columns to fold into llm_context per source.",
    )
    parser.add_argument(
        "--disable-llm-deduction",
        action="store_true",
        help="Disable local LLM-based alias deduction during batch mapping.",
    )
    parser.add_argument(
        "--llm-models",
        default="",
        help="Comma-separated local model ids for LLM deduction priority.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Optional directory for caching downloaded remote sources (OSF/GitHub/web datasets).",
    )
    parser.add_argument(
        "--refresh-remote-cache",
        action="store_true",
        help="Force re-download of remote sources instead of using the cache.",
    )
    parser.add_argument(
        "--debug-mappings",
        action="store_true",
        help="Write per-dataset mapping debug artifacts during batch standardization.",
    )
    args = parser.parse_args()

    preferred_models = [item.strip() for item in args.llm_models.split(",") if item.strip()] or None
    summary = run_catalog_meta_analysis(
        catalog_path=args.catalog,
        url_column=args.url_column,
        output_dir=args.output_dir,
        sheet_name=_coerce_sheet_name(args.sheet_name),
        schema_path=args.schema,
        source_id_column=args.source_id_column,
        source_type_column=args.source_type_column,
        context_columns=_parse_context_columns(args.context_columns),
        llm_deduction_enabled=not args.disable_llm_deduction,
        cache_dir=args.cache_dir,
        refresh_remote_cache=args.refresh_remote_cache,
        preferred_models=preferred_models,
        debug_mappings=args.debug_mappings,
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
