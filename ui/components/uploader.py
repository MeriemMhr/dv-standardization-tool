"""
uploader.py

Reusable uploader component for the OpenDV-HCI Streamlit interface.
Encapsulates upload logic, file validation, and error handling.
"""

import streamlit as st
import pandas as pd

def upload_csv():
    st.sidebar.header("Upload CSV Dataset")
    uploaded_file = st.sidebar.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.sidebar.success("File uploaded successfully!")
            return df
        except Exception as e:
            st.sidebar.error(f"Failed to read CSV: {e}")
            return None
    else:
        return None
