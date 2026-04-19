#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
PREFERRED_INPUT_DIR="data/processed/batch_runs/latest/standardized"
FALLBACK_INPUT_DIR="data/processed/multi_study_examples"
OUTPUT_DIR="${1:-analyses/output_python_latest_standardized}"

if [ -d "$PREFERRED_INPUT_DIR" ] && find "$PREFERRED_INPUT_DIR" -maxdepth 2 -type f \( -name '*.csv' -o -name '*.xlsx' \) | grep -q .; then
  INPUT_DIR="$PREFERRED_INPUT_DIR"
  echo "Using latest standardized batch datasets: $INPUT_DIR"
else
  INPUT_DIR="$FALLBACK_INPUT_DIR"
  echo "Latest standardized batch datasets not found/empty at $PREFERRED_INPUT_DIR"
  echo "Falling back to bundled example datasets: $INPUT_DIR"
fi

"$PYTHON_BIN" -m pip install --upgrade pip pandas numpy matplotlib seaborn scikit-learn openpyxl
"$PYTHON_BIN" analyses/multi_study_analysis.py --input-dir "$INPUT_DIR" --output-dir "$OUTPUT_DIR"

echo "Analysis complete. Outputs written to: $OUTPUT_DIR"
