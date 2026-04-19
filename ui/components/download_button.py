"""Reusable download button logic for tabular outputs in the Streamlit UI."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st


def render_download_button(df, filename: str = "standardized_output.csv"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Cleaned Dataset",
        data=csv,
        file_name=filename,
        mime="text/csv",
    )


def render_table_download_buttons(
    df,
    file_stem: str,
    key_prefix: str,
    csv_label: str = "Download CSV",
    excel_label: str = "Download Excel",
) -> None:
    csv_data = df.to_csv(index=False).encode("utf-8")
    left, right = st.columns(2)
    left.download_button(
        csv_label,
        data=csv_data,
        file_name=f"{file_stem}.csv",
        mime="text/csv",
        key=f"{key_prefix}_csv",
    )

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    right.download_button(
        excel_label,
        data=excel_buffer.getvalue(),
        file_name=f"{file_stem}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}_xlsx",
    )
