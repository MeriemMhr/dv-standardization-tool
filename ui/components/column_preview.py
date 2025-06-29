"""
column_preview.py

Reusable component for visualizing original vs standardized column names
in the OpenDV-HCI Streamlit interface.
"""

import streamlit as st
import pandas as pd

def show_column_comparison(df_raw, df_standardized):
    if df_raw is not None and df_standardized is not None:
        st.subheader("Before and After: Column Name Mapping")

        # Prepare comparison DataFrame
        raw_cols = pd.Series(df_raw.columns, name="Original Columns")
        std_cols = pd.Series(df_standardized.columns, name="Standardized Columns")

        df_compare = pd.concat([raw_cols, std_cols], axis=1)
        st.dataframe(df_compare)

        match_rate = sum(raw_cols != std_cols) / len(raw_cols)
        st.markdown(f"**Mapping Change Rate**: {match_rate:.2%} of columns renamed")
