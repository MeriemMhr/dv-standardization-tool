"""
column_preview.py

Reusable component for visualizing original vs standardized column names
in the OpenDV-HCI Streamlit interface.
"""

import streamlit as st
import pandas as pd


def build_column_comparison_df(df_raw, df_standardized) -> pd.DataFrame:
    raw_cols = pd.Series(df_raw.columns, name="Original Columns")
    std_cols = pd.Series(df_standardized.columns, name="Standardized Columns")
    comparison = pd.concat([raw_cols, std_cols], axis=1)
    comparison["Changed"] = comparison["Original Columns"] != comparison["Standardized Columns"]
    return comparison


def show_column_comparison(df_raw, df_standardized):
    if df_raw is not None and df_standardized is not None:
        st.subheader("Before and After: Column Name Mapping")
        comparison = build_column_comparison_df(df_raw, df_standardized)
        st.dataframe(comparison, use_container_width=True)
        change_rate = comparison["Changed"].mean() if len(comparison) else 0.0
        st.markdown(f"**Mapping Change Rate**: {change_rate:.2%} of columns renamed")
