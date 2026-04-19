"""Interactive chart builders for the Streamlit UI."""

from __future__ import annotations

import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go
except Exception:  # noqa: BLE001
    px = None
    go = None


def _require_plotly() -> None:
    if px is None or go is None:
        raise ImportError(
            "Plotly is required for interactive charts. Install UI dependencies with "
            "`pip install -r requirements-core.txt -r requirements-ui.txt`."
        )


def build_mapping_quality_chart(mapped_columns: int, unknown_columns: int):
    _require_plotly()
    df = pd.DataFrame(
        {
            "status": ["Mapped", "Unmapped"],
            "count": [mapped_columns, unknown_columns],
        }
    )
    return px.bar(
        df,
        x="status",
        y="count",
        color="status",
        color_discrete_map={"Mapped": "#2d6a4f", "Unmapped": "#bc4749"},
        title="Column Mapping Quality",
    )


def build_overlap_heatmap(overlap_df: pd.DataFrame, title: str = "DV Overlap (Jaccard)"):
    _require_plotly()
    return go.Figure(
        data=go.Heatmap(
            z=overlap_df.values,
            x=list(overlap_df.columns),
            y=list(overlap_df.index),
            colorscale="Blues",
            zmin=0,
            zmax=1,
            text=overlap_df.round(2).astype(str).values,
            texttemplate="%{text}",
            hovertemplate="Study X: %{x}<br>Study Y: %{y}<br>Overlap: %{z:.2f}<extra></extra>",
        )
    ).update_layout(title=title, xaxis_title="Study", yaxis_title="Study")


def build_presence_heatmap(presence_df: pd.DataFrame):
    _require_plotly()
    return go.Figure(
        data=go.Heatmap(
            z=presence_df.values,
            x=list(presence_df.columns),
            y=list(presence_df.index),
            colorscale=[[0.0, "#f1faee"], [1.0, "#1d3557"]],
            zmin=0,
            zmax=1,
            hovertemplate="Study: %{y}<br>DV: %{x}<br>Present: %{z}<extra></extra>",
        )
    ).update_layout(title="DV Presence Across Studies", xaxis_title="Dependent Variable", yaxis_title="Study")


def build_meta_analysis_chart(meta_df: pd.DataFrame):
    _require_plotly()
    if meta_df.empty:
        return None

    ordered = meta_df.sort_values("random_effects_mean").copy()
    error_x = ordered["ci95_high"] - ordered["random_effects_mean"]
    error_x_minus = ordered["random_effects_mean"] - ordered["ci95_low"]

    fig = go.Figure(
        data=go.Scatter(
            x=ordered["random_effects_mean"],
            y=ordered["dv"],
            mode="markers",
            marker=dict(size=10, color=ordered["study_coverage_pct"], colorscale="Tealgrn", showscale=True),
            error_x=dict(
                type="data",
                symmetric=False,
                array=error_x,
                arrayminus=error_x_minus,
            ),
            text=ordered["k_studies"],
            hovertemplate=(
                "DV: %{y}<br>Random-effects mean: %{x:.3f}"
                "<br>95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]"
                "<br>Studies: %{text}<extra></extra>"
            ),
            customdata=ordered[["ci95_low", "ci95_high"]].values,
        )
    )
    fig.update_layout(
        title="Meta-analysis Summary",
        xaxis_title="Random-effects mean",
        yaxis_title="Dependent Variable",
    )
    return fig


def build_overlap_detail_chart(overlap_details_df: pd.DataFrame):
    _require_plotly()
    if overlap_details_df.empty:
        return None
    chart_df = overlap_details_df.copy()
    chart_df["pair"] = chart_df["study_a"] + " vs " + chart_df["study_b"]
    return px.bar(
        chart_df,
        x="pair",
        y="jaccard_overlap",
        color="shared_dv_count",
        color_continuous_scale="Tealgrn",
        title="Pairwise Study Overlap",
    )
