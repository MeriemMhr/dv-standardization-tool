"""
app.py

Streamlit-based UI for the OpenDV-HCI tool. Users can upload raw datasets,
preview column standardization based on the YAML schema, and download the cleaned result.
"""

import streamlit as st
import pandas as pd
import yaml
import io

from scripts.convert_dv import standardize_columns

st.set_page_config(page_title="OpenDV-HCI Tool", layout="wide")

st.title("OpenDV-HCI: Dependent Variable Standardization Tool")

# Upload CSV
uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    st.subheader("Original Column Names")
    st.dataframe(pd.DataFrame(df_raw.columns, columns=["Column Names"]))

    # Load schema
    try:
        with open("schemas/standard_dv_mapping.yaml", "r") as f:
            schema = yaml.safe_load(f)
    except FileNotFoundError:
        st.error("Schema file not found. Please ensure schemas/standard_dv_mapping.yaml exists.")
        st.stop()

    # Apply standardization
    df_clean = standardize_columns(df_raw.copy(), schema)
    st.subheader("Standardized Column Names")
    st.dataframe(pd.DataFrame(df_clean.columns, columns=["Column Names"]))

    # Download cleaned version
    st.subheader("Download")
    csv_download = df_clean.to_csv(index=False).encode('utf-8')
    st.download_button("Download Standardized CSV", data=csv_download, file_name="standardized_output.csv")

st.markdown("---")
st.markdown("This is a minimal prototype to support reproducibility in HCI open data workflows.")
