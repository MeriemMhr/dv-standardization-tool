"""
convert_dv.py

This script standardizes dependent variable (DV) names in a dataset by applying
a canonical mapping defined in a YAML schema. It also infers measurement metadata
(category, units, scale type) for each column and exports this as a JSON sidecar file.

Part of the OpenDV-HCI project for promoting reproducibility and interoperability
in HCI research.

Usage:
    python convert_dv.py --input path/to/input.csv --output path/to/output.csv
    python convert_dv.py --input data.csv --output standardized.csv --with-metadata
"""

import argparse
import json
import pandas as pd
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

# Import the new inference module
try:
    from dv_inference import batch_infer, get_measurement_from_schema, load_inference_rules
except ImportError:
    print("Warning: dv_inference module not found. Metadata inference will be disabled.")
    batch_infer = None


def load_schema(schema_path: str) -> Dict:
    """
    Load the DV mapping schema from YAML.

    Args:
        schema_path: Path to standard_dv_mapping.yaml

    Returns:
        Dictionary with alias_to_standard mapping and full schema
    """
    with open(schema_path, "r") as f:
        schema = yaml.safe_load(f)

    alias_to_standard = {}

    # Handle new schema format (version 2.1+) with 'dvs' list
    if 'dvs' in schema:
        for dv in schema['dvs']:
            standard_name = dv.get('id')
            aliases = dv.get('aliases', [])
            for alias in aliases:
                alias_to_standard[alias] = standard_name
            # Also map the id itself
            alias_to_standard[standard_name] = standard_name
    else:
        # Legacy format: flat dict {standard_name: [aliases]}
        for standard, aliases in schema.items():
            if isinstance(aliases, list):
                for alias in aliases:
                    alias_to_standard[alias] = standard

    return {"mapping": alias_to_standard, "schema": schema}


def standardize_columns(df: pd.DataFrame, mapping: Dict) -> pd.DataFrame:
    """
    Rename DataFrame columns using the alias mapping.

    Args:
        df: Input DataFrame with raw column names
        mapping: Alias -> standard name dictionary

    Returns:
        DataFrame with standardized column names
    """
    new_columns = []
    for col in df.columns:
        new_columns.append(mapping.get(col, col))  # Default to original if not found
    df.columns = new_columns
    return df


def standardize_with_metadata(
    df: pd.DataFrame,
    mapping: Dict,
    schema: Dict,
    confidence_threshold: float = 0.7
) -> Tuple[pd.DataFrame, Dict]:
    """
    Standardize columns and infer measurement types.

    Args:
        df: Input DataFrame with raw column names
        mapping: Alias -> standard name mapping
        schema: Full schema dictionary
        confidence_threshold: Minimum confidence for auto-accept

    Returns:
        (standardized_df, column_metadata)
    """
    # Step 1: Rename columns (existing logic)
    standardized_df = df.rename(columns=lambda col: mapping.get(col, col))

    # Step 2: Infer measurement types for all columns
    column_meta = {}

    if batch_infer is None:
        # If inference module not available, return basic metadata
        for col in standardized_df.columns:
            column_meta[col] = {
                "original_name": [k for k, v in mapping.items() if v == col] or [col],
                "inference_available": False
            }
        return standardized_df, column_meta

    # Try to get metadata from schema first (ground truth)
    for col in standardized_df.columns:
        # Check if this column has schema-defined metadata
        schema_meta = get_measurement_from_schema(col)

        if schema_meta:
            # Use schema-defined metadata (highest confidence)
            column_meta[col] = {
                **schema_meta.to_dict(),
                "original_name": [k for k, v in mapping.items() if v == col] or [col]
            }
        else:
            # Infer metadata for columns not in schema
            inferences = batch_infer([col], confidence_threshold)
            _, meta, needs_review = inferences[0]
            column_meta[col] = {
                **meta.to_dict(),
                "original_name": [k for k, v in mapping.items() if v == col] or [col]
            }

    return standardized_df, column_meta


def export_with_metadata(
    df: pd.DataFrame,
    column_meta: Dict,
    output_path: str,
    schema_version: str = "2.1"
) -> None:
    """
    Export CSV with sidecar metadata JSON.

    Creates:
        - output_path: Standardized CSV
        - output_path_metadata.json: Column metadata
    """
    # Export CSV
    df.to_csv(output_path, index=False)
    print(f"✓ Standardized CSV saved to: {output_path}")

    # Export metadata JSON
    meta_path = str(Path(output_path).with_suffix('')) + "_metadata.json"
    metadata = {
        "schema_version": schema_version,
        "inference_timestamp": datetime.now().isoformat(),
        "columns": column_meta,
        "summary": {
            "total_columns": len(column_meta),
            "needs_review": sum(
                1 for m in column_meta.values()
                if m.get("needs_review", False)
            ),
            "categories": {}
        }
    }

    # Count categories
    for col, meta in column_meta.items():
        cat = meta.get("category", "Unknown")
        metadata["summary"]["categories"][cat] = metadata["summary"]["categories"].get(cat, 0) + 1

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ Metadata JSON saved to: {meta_path}")

    # Warn if columns need review
    if metadata["summary"]["needs_review"] > 0:
        print(f"⚠ Warning: {metadata['summary']['needs_review']} column(s) flagged for manual review (low confidence)")


def main():
    parser = argparse.ArgumentParser(
        description="Standardize DV column names and infer measurement metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (column renaming only):
  python convert_dv.py --input data.csv --output standardized.csv

  # With measurement metadata inference:
  python convert_dv.py --input data.csv --output standardized.csv --with-metadata

  # Custom schema file:
  python convert_dv.py --input data.csv --output out.csv --schema custom_schema.yaml
        """
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input CSV file"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to save the standardized CSV file"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default="../schemas/standard_dv_mapping.yaml",
        help="Path to YAML schema file (default: ../schemas/standard_dv_mapping.yaml)"
    )
    parser.add_argument(
        "--with-metadata",
        action="store_true",
        help="Infer and export measurement metadata (category, units, scale type)"
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Minimum confidence threshold for auto-accepting inferences (default: 0.7)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("OpenDV-HCI: DV Standardization Tool")
    print("=" * 60)

    # Load CSV
    print(f"Loading input file: {args.input}")
    df = pd.read_csv(args.input)
    print(f"  ✓ Loaded {len(df)} rows, {len(df.columns)} columns")

    # Load schema and build mapping
    print(f"Loading schema: {args.schema}")
    schema_data = load_schema(args.schema)
    mapping = schema_data["mapping"]
    schema = schema_data["schema"]
    print(f"  ✓ Loaded {len(mapping)} alias mappings")

    # Apply standardization
    if args.with_metadata:
        print("Standardizing columns and inferring measurement metadata...")
        df_standardized, column_meta = standardize_with_metadata(
            df,
            mapping,
            schema,
            args.confidence_threshold
        )
        export_with_metadata(df_standardized, column_meta, args.output, schema.get('version', '2.1'))
    else:
        print("Standardizing columns (metadata inference disabled)...")
        df_standardized = standardize_columns(df, mapping)
        df_standardized.to_csv(args.output, index=False)
        print(f"✓ Standardized file saved to: {args.output}")

    print("=" * 60)
    print("✓ Standardization complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
