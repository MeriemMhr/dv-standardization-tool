"""
download_button.py

Reusable download button logic for standardized CSV outputs in the OpenDV-HCI Streamlit interface.
"""

import streamlit as st

def render_download_button(df, filename="standardized_output.csv"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Cleaned Dataset",
        data=csv,
        file_name=filename,
        mime="text/csv"
    )
