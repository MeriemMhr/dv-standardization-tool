"""
convert_dv.py

This script standardizes dependent variable (DV) names in a dataset by applying
a canonical mapping defined in a YAML schema. It is part of the DV Standardization Tool
for promoting reproducibility and interoperability in HCI research.

Usage:
    python convert_dv.py --input path/to/input.csv --output path/to/output.csv
"""

import argparse
import pandas as pd
import yaml


def load_schema(schema_path):
    with open(schema_path, "r") as f:
        schema = yaml.safe_load(f)
    alias_to_standard = {}
    for standard, aliases in schema.items():
        for alias in aliases:
            alias_to_standard[alias] = standard
    return alias_to_standard


def standardize_columns(df, mapping):
    new_columns = []
    for col in df.columns:
        new_columns.append(mapping.get(col, col))  # Default to original if not found
    df.columns = new_columns
    return df


def main():
    parser = argparse.ArgumentParser(description="Standardize DV column names using a mapping schema.")
    parser.add_argument("--input", type=str, required=True, help="Path to input CSV file")
    parser.add_argument("--output", type=str, required=True, help="Path to save the standardized CSV file")
    parser.add_argument("--schema", type=str, default="../schemas/standard_dv_mapping.yaml",
                        help="Path to YAML schema file (default: ../schemas/standard_dv_mapping.yaml)")

    args = parser.parse_args()

    # Load CSV
    df = pd.read_csv(args.input)

    # Load schema and build mapping
    mapping = load_schema(args.schema)

    # Apply standardization
    df_standardized = standardize_columns(df, mapping)

    # Save the result
    df_standardized.to_csv(args.output, index=False)
    print(f"Standardized file saved to {args.output}")


if __name__ == "__main__":
    main()
