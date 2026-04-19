"""
reshape_utils.py

Utilities for detecting and reshaping data between long and wide formats.

The OpenDV-HCI standardization pipeline expects wide-format data (one row per
participant, one column per DV).  Many HCI datasets, however, arrive in long
format (one row per observation with a "variable"/"measure" column and a
"value" column).  This module provides heuristic detection and automated
reshaping so that upstream scripts can work with a uniform wide layout.

Usage:
    from scripts.reshape_utils import auto_reshape_to_wide, detect_data_shape
"""

import logging
import re
import warnings
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants used by the heuristics
# ---------------------------------------------------------------------------

# Column names that strongly suggest the column holds variable/measure labels
_VARIABLE_COL_NAMES: set[str] = {
    "variable", "measure", "item", "condition", "metric",
    "dv", "dv_name", "dependent_variable", "scale", "factor",
    "question", "questionnaire_item",
}

# Column names that strongly suggest the column holds observed values
_VALUE_COL_NAMES: set[str] = {
    "value", "score", "response", "result", "rating",
    "measurement", "answer", "outcome",
}

# Column names that strongly suggest a participant / subject identifier
_ID_COL_NAMES: set[str] = {
    "id", "participant", "participant_id", "subject", "subject_id",
    "pid", "sid", "respondent", "respondent_id", "user", "user_id",
}

# When the ratio  unique_values / n_rows  is below this threshold for a
# string column we treat it as a candidate variable column.
_VARIABLE_UNIQUENESS_RATIO: float = 0.25

# If a DataFrame has fewer columns than this it is more likely to be long
_LONG_FORMAT_MAX_COLS: int = 8

# If a DataFrame has more columns than this it is more likely to be wide
_WIDE_FORMAT_MIN_COLS: int = 15


def _normalize(name: str) -> str:
    """Lower-case, strip, collapse whitespace / underscores for comparison."""
    return re.sub(r"[\s_]+", "_", str(name).strip().lower())


# ---- public API -----------------------------------------------------------

def detect_data_shape(df: pd.DataFrame) -> Literal["wide", "long", "ambiguous"]:
    """Detect whether *df* is in wide or long format.

    Heuristics
    ----------
    * **Long-format indicators** -- few columns; presence of a column whose
      name matches known variable-name patterns *and* a companion numeric
      value column; many unique values in the variable column relative to
      the overall row count.
    * **Wide-format indicators** -- many columns with DV-like names; few
      rows per unique ID value.
    * Returns ``"ambiguous"`` when the signals are mixed or too weak.

    Parameters
    ----------
    df : pd.DataFrame
        Input data to classify.

    Returns
    -------
    Literal["wide", "long", "ambiguous"]
    """
    if df.empty:
        logger.warning("detect_data_shape called on an empty DataFrame.")
        return "ambiguous"

    n_rows, n_cols = df.shape
    norm_cols = {_normalize(c): c for c in df.columns}

    long_score = 0
    wide_score = 0

    # --- Structural signals ------------------------------------------------
    if n_cols <= _LONG_FORMAT_MAX_COLS:
        long_score += 1
    if n_cols >= _WIDE_FORMAT_MIN_COLS:
        wide_score += 2

    # --- Name-based signals ------------------------------------------------
    has_variable_col = bool(_VARIABLE_COL_NAMES & set(norm_cols))
    has_value_col = bool(_VALUE_COL_NAMES & set(norm_cols))
    has_id_col = bool(_ID_COL_NAMES & set(norm_cols))

    if has_variable_col and has_value_col:
        long_score += 3
    elif has_variable_col:
        long_score += 1
    elif has_value_col:
        long_score += 1

    # --- Content-based signals ---------------------------------------------
    # Look for string columns with moderate cardinality (variable-like)
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            n_unique = df[col].nunique()
            ratio = n_unique / max(n_rows, 1)
            if _VARIABLE_UNIQUENESS_RATIO < ratio < 0.8 and n_unique >= 3:
                # Could be a variable column -- mild long signal
                long_score += 1
                break  # count only once

    # Wide signal: many numeric columns that are not obviously id-like
    numeric_cols = df.select_dtypes(include="number").columns
    non_id_numeric = [
        c for c in numeric_cols if _normalize(c) not in _ID_COL_NAMES
    ]
    if len(non_id_numeric) >= 5:
        wide_score += 2

    # Check rows-per-id ratio when an ID column is present
    if has_id_col:
        id_col_name = next(
            norm_cols[n] for n in norm_cols if n in _ID_COL_NAMES
        )
        rows_per_id = n_rows / max(df[id_col_name].nunique(), 1)
        if rows_per_id > 3:
            long_score += 2
        elif rows_per_id <= 1.5:
            wide_score += 1

    # --- Decision ----------------------------------------------------------
    logger.debug(
        "detect_data_shape  long_score=%d  wide_score=%d  cols=%d",
        long_score, wide_score, n_cols,
    )

    diff = long_score - wide_score
    if diff >= 2:
        return "long"
    if diff <= -2:
        return "wide"
    return "ambiguous"


def detect_long_format_columns(df: pd.DataFrame) -> Dict[str, Any]:
    """Auto-detect which columns serve as ID, variable name, and value.

    Uses a combination of column-name matching and content heuristics:

    * **id_col** -- column with the fewest unique values relative to row
      count, or a column whose name matches known ID patterns.
    * **variable_col** -- string column whose values look like variable
      names (moderate cardinality), or a column whose name matches known
      variable-name patterns.
    * **value_col** -- numeric column, or a column whose name matches known
      value patterns.
    * **extra_cols** -- all remaining columns.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    dict
        ``{"id_col": str | None, "variable_col": str | None,
        "value_col": str | None, "extra_cols": list[str]}``
    """
    norm_cols = {_normalize(c): c for c in df.columns}
    n_rows = len(df)

    id_col: Optional[str] = None
    variable_col: Optional[str] = None
    value_col: Optional[str] = None

    # --- Pass 1: name-based matching (strongest signal) --------------------
    for norm, raw in norm_cols.items():
        if norm in _ID_COL_NAMES and id_col is None:
            id_col = raw
        elif norm in _VARIABLE_COL_NAMES and variable_col is None:
            variable_col = raw
        elif norm in _VALUE_COL_NAMES and value_col is None:
            value_col = raw

    # --- Pass 2: content-based heuristics for any still-missing role -------
    assigned = {id_col, variable_col, value_col} - {None}

    if variable_col is None:
        # Pick the string column with moderate cardinality
        best_candidate: Optional[str] = None
        best_score: float = -1.0
        for col in df.columns:
            if col in assigned:
                continue
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                n_unique = df[col].nunique()
                ratio = n_unique / max(n_rows, 1)
                # Prefer columns with a ratio in the "variable-like" range
                if 0.01 < ratio < 0.8 and n_unique >= 2:
                    score = n_unique  # more distinct values = more variable-like
                    if score > best_score:
                        best_score = score
                        best_candidate = col
        if best_candidate is not None:
            variable_col = best_candidate
            assigned.add(variable_col)

    if value_col is None:
        # Pick the first numeric column not already assigned
        for col in df.select_dtypes(include="number").columns:
            if col not in assigned:
                value_col = col
                assigned.add(value_col)
                break

    if id_col is None:
        # Pick the column with the fewest unique values (excluding already assigned)
        best_candidate = None
        best_ratio: float = 2.0  # impossible high ratio
        for col in df.columns:
            if col in assigned:
                continue
            ratio = df[col].nunique() / max(n_rows, 1)
            if ratio < best_ratio:
                best_ratio = ratio
                best_candidate = col
        if best_candidate is not None:
            id_col = best_candidate
            assigned.add(id_col)

    extra_cols = [c for c in df.columns if c not in assigned]

    result = {
        "id_col": id_col,
        "variable_col": variable_col,
        "value_col": value_col,
        "extra_cols": extra_cols,
    }
    logger.info("detect_long_format_columns result: %s", result)
    return result


def long_to_wide(
    df: pd.DataFrame,
    id_col: str,
    variable_col: str,
    value_col: str,
    aggfunc: Union[str, Callable] = "mean",
) -> pd.DataFrame:
    """Pivot a long-format DataFrame to wide format.

    Parameters
    ----------
    df : pd.DataFrame
        Long-format data.
    id_col : str
        Column identifying the participant / subject.
    variable_col : str
        Column containing the DV / measure names.
    value_col : str
        Column containing the observed values.
    aggfunc : str or callable, default ``"mean"``
        Aggregation function used when there are duplicate entries for the
        same (id, variable) pair.  Passed directly to
        :func:`pandas.pivot_table`.

    Returns
    -------
    pd.DataFrame
        Wide-format DataFrame with *id_col* as the index (reset to a
        regular column) and one column per unique value in *variable_col*.

    Raises
    ------
    KeyError
        If any of the specified columns are not present in *df*.
    """
    for col_name, col_label in [
        (id_col, "id_col"),
        (variable_col, "variable_col"),
        (value_col, "value_col"),
    ]:
        if col_name not in df.columns:
            raise KeyError(
                f"{col_label}={col_name!r} not found in DataFrame columns "
                f"{list(df.columns)}"
            )

    # Coerce value column to numeric where possible
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    n_before = len(df)
    n_null = df[value_col].isna().sum()
    if n_null > 0:
        logger.warning(
            "long_to_wide: %d of %d values could not be coerced to numeric "
            "and will be treated as NaN.",
            n_null, n_before,
        )

    # Detect whether variable_col contains multi-level keys
    # (e.g. "condition_A__trust_score") separated by a common delimiter.
    sample_values = df[variable_col].dropna().unique()
    delimiter: Optional[str] = None
    for sep in ("__", "::", " - ", "/"):
        if all(sep in str(v) for v in sample_values[:20]):
            delimiter = sep
            break

    if delimiter is not None:
        logger.info(
            "long_to_wide: detected multi-level variable names with "
            "delimiter %r -- creating hierarchical column names.",
            delimiter,
        )
        # Split into separate columns for a multi-index pivot
        parts = df[variable_col].str.split(delimiter, n=1, expand=True)
        level_cols: list[str] = []
        for i in range(parts.shape[1]):
            col = f"_reshape_level_{i}"
            df[col] = parts[i].str.strip()
            level_cols.append(col)

        wide = pd.pivot_table(
            df,
            index=id_col,
            columns=level_cols,
            values=value_col,
            aggfunc=aggfunc,
        )
        # Flatten multi-level column index into single strings
        wide.columns = [
            delimiter.join(str(c) for c in col_tuple).strip()
            if isinstance(col_tuple, tuple)
            else str(col_tuple)
            for col_tuple in wide.columns
        ]
    else:
        wide = pd.pivot_table(
            df,
            index=id_col,
            columns=variable_col,
            values=value_col,
            aggfunc=aggfunc,
        )
        # Flatten column name (single level)
        wide.columns = [str(c) for c in wide.columns]

    wide = wide.reset_index()

    logger.info(
        "long_to_wide: reshaped %d rows x %d cols -> %d rows x %d cols",
        n_before, df.shape[1], wide.shape[0], wide.shape[1],
    )
    return wide


def wide_to_long(
    df: pd.DataFrame,
    id_col: str,
    value_vars: Sequence[str],
    var_name: str = "variable",
    value_name: str = "value",
) -> pd.DataFrame:
    """Melt a wide-format DataFrame to long format.

    Parameters
    ----------
    df : pd.DataFrame
        Wide-format data.
    id_col : str
        Column identifying the participant / subject (kept as-is).
    value_vars : sequence of str
        Columns to unpivot into rows.
    var_name : str, default ``"variable"``
        Name for the new variable-name column.
    value_name : str, default ``"value"``
        Name for the new value column.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame.

    Raises
    ------
    KeyError
        If *id_col* or any entry in *value_vars* is missing from *df*.
    """
    if id_col not in df.columns:
        raise KeyError(
            f"id_col={id_col!r} not found in DataFrame columns "
            f"{list(df.columns)}"
        )
    missing = [v for v in value_vars if v not in df.columns]
    if missing:
        raise KeyError(
            f"value_vars not found in DataFrame: {missing}"
        )

    long = pd.melt(
        df,
        id_vars=[id_col],
        value_vars=list(value_vars),
        var_name=var_name,
        value_name=value_name,
    )

    logger.info(
        "wide_to_long: reshaped %d rows x %d cols -> %d rows x %d cols",
        df.shape[0], df.shape[1], long.shape[0], long.shape[1],
    )
    return long


def auto_reshape_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Detect the shape of *df* and, if long, reshape to wide format.

    This is the main convenience entry-point intended for use by the
    standardization pipeline.  If the data is already wide or the shape
    is ambiguous the DataFrame is returned unchanged (with a warning in
    the latter case).

    Parameters
    ----------
    df : pd.DataFrame
        Input data in any layout.

    Returns
    -------
    pd.DataFrame
        Wide-format DataFrame (possibly unchanged).
    """
    shape = detect_data_shape(df)

    if shape == "wide":
        logger.info("auto_reshape_to_wide: data is already in wide format.")
        return df

    if shape == "ambiguous":
        warnings.warn(
            "auto_reshape_to_wide: data shape is ambiguous -- returning "
            "DataFrame unchanged.  Consider reshaping manually.",
            UserWarning,
            stacklevel=2,
        )
        logger.warning(
            "auto_reshape_to_wide: ambiguous shape (%d rows x %d cols). "
            "Returning data as-is.",
            df.shape[0], df.shape[1],
        )
        return df

    # shape == "long"
    col_info = detect_long_format_columns(df)
    id_col = col_info["id_col"]
    variable_col = col_info["variable_col"]
    value_col = col_info["value_col"]

    if id_col is None or variable_col is None or value_col is None:
        warnings.warn(
            "auto_reshape_to_wide: detected long format but could not "
            f"identify all required columns (id={id_col}, "
            f"variable={variable_col}, value={value_col}).  "
            "Returning DataFrame unchanged.",
            UserWarning,
            stacklevel=2,
        )
        return df

    logger.info(
        "auto_reshape_to_wide: detected long format -- pivoting with "
        "id=%r, variable=%r, value=%r.",
        id_col, variable_col, value_col,
    )
    return long_to_wide(df, id_col, variable_col, value_col)
