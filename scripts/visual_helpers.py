"""
visual_helpers.py

Helper functions for visualizing column name transformations and dataset coverage
in the DV Standardization Tool.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd


def plot_column_comparison(original_df, standardized_df):
    """
    Plot side-by-side comparison of original vs standardized column names.

    Args:
        original_df (pd.DataFrame): DataFrame with original column names.
        standardized_df (pd.DataFrame): DataFrame with standardized column names.
    """
    original_cols = original_df.columns.tolist()
    standardized_cols = standardized_df.columns.tolist()

    df_compare = pd.DataFrame({
        'Original Column': original_cols,
        'Standardized Column': standardized_cols
    })

    fig, ax = plt.subplots(figsize=(10, len(df_compare) * 0.4))
    ax.axis('off')
    table = ax.table(cellText=df_compare.values,
                     colLabels=df_compare.columns,
                     cellLoc='left',
                     loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    plt.title("Column Name Transformation Overview", fontsize=14, weight='bold')
    plt.tight_layout()
    plt.show()


def plot_schema_coverage(raw_df, known_aliases):
    """
    Visualize the coverage of the schema over the raw dataset columns.

    Args:
        raw_df (pd.DataFrame): Raw input DataFrame.
        known_aliases (set): Set of all aliases captured in the schema.
    """
    raw_columns = set(raw_df.columns)
    matched = raw_columns & known_aliases
    unmatched = raw_columns - known_aliases

    counts = {'Matched': len(matched), 'Unmatched': len(unmatched)}
    sns.barplot(x=list(counts.keys()), y=list(counts.values()), palette="pastel")
    plt.ylabel("Number of Columns")
    plt.title("Schema Coverage of Raw Dataset Columns")
    plt.tight_layout()
    plt.show()
