"""
Visualizations module.
Provides polished, interactive Plotly charts with a modern analytics theme.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Brand Color Palette
COLORS = {
    "primary": "#2563EB",  # Royal Blue
    "secondary": "#4F46E5",  # Indigo
    "success": "#10B981",  # Emerald Green
    "warning": "#F59E0B",  # Amber
    "danger": "#EF4444",  # Crimson Red
    "info": "#06B6D4",  # Cyan
    "purple": "#8B5CF6",  # Violet
    "dark": "#1E293B",  # Slate 800
    "light": "#F8FAFC",  # Slate 50
    "grid": "#E2E8F0",  # Slate 200
    "text": "#0F172A",  # Slate 900
    "muted": "#64748B",  # Slate 500
}

SEGMENT_COLORS = {
    "Champions": "#10B981",
    "Loyal Customers": "#2563EB",
    "New / Potential Loyalists": "#06B6D4",
    "Promising / Regular": "#8B5CF6",
    "At Risk (High Spenders)": "#F59E0B",
    "Can't Lose Them": "#EC4899",
    "About to Sleep": "#F97316",
    "Lost Customers": "#EF4444",
    "Hibernating": "#94A3B8",
}

TEMPLATE = "plotly_white"


def _apply_theme(fig: go.Figure, title: str = "", height: int = 420) -> go.Figure:
    """Apply consistent modern typography, margins, and gridlines to Plotly figures."""
    fig.update_layout(
        template=TEMPLATE,
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=16, color=COLORS["text"], family="Inter, system-ui, sans-serif"),
            x=0.01,
            y=0.96,
        ),
        font=dict(family="Inter, system-ui, sans-serif", color=COLORS["dark"], size=12),
        margin=dict(l=40, r=40, t=60, b=40),
        height=height,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Inter, system-ui, sans-serif",
            bordercolor=COLORS["grid"],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)",
        ),
        xaxis=dict(showgrid=True, gridcolor=COLORS["grid"], zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], zeroline=False),
    )
    return fig


def plot_revenue_trend(trend_df: pd.DataFrame, title: str = "Revenue Trajectory Over Time") -> go.Figure:
    """Line chart showing Gross, Net Revenue, and Refunds with moving average."""
    if trend_df.empty:
        return go.Figure()

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=trend_df["period"],
            y=trend_df["gross_revenue"],
            name="Gross Sales",
            mode="lines",
            line=dict(color=COLORS["muted"], width=1.5, dash="dot"),
            hovertemplate="<b>Gross Sales:</b> £%{y:,.2f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=trend_df["period"],
            y=trend_df["net_revenue"],
            name="Net Revenue",
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=2.5),
            marker=dict(size=5, color=COLORS["primary"]),
            hovertemplate="<b>Net Revenue:</b> £%{y:,.2f}<br><b>Date:</b> %{x|%b %Y}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            x=trend_df["period"],
            y=trend_df["refund_amount"],
            name="Returns / Refunds",
            marker_color=COLORS["danger"],
            opacity=0.65,
            hovertemplate="<b>Returns:</b> £%{y:,.2f}<extra></extra>",
        )
    )

    fig.update_layout(barmode="overlay")
    return _apply_theme(fig, title=title)


def plot_top_products(
    prod_df: pd.DataFrame, metric: str = "net_revenue", title: str = "Top Products by Net Revenue"
) -> go.Figure:
    """Horizontal bar chart for top products with return rates."""
    if prod_df.empty:
        return go.Figure()

    df_sorted = prod_df.sort_values(metric, ascending=True).tail(12)
    # Truncate description for display
    df_sorted["display_label"] = (
        df_sorted["description"].str.slice(0, 26) + " (" + df_sorted["StockCode"] + ")"
    )

    fig = go.Figure(
        go.Bar(
            y=df_sorted["display_label"],
            x=df_sorted[metric],
            orientation="h",
            marker=dict(
                color=df_sorted[metric],
                colorscale="Blues",
                showscale=False,
            ),
            customdata=np.stack(
                (
                    df_sorted["units_sold"],
                    df_sorted["units_returned"],
                    df_sorted["return_rate_rev_pct"],
                    df_sorted["gross_sales"],
                ),
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                + f"<b>{metric.replace('_', ' ').title()}:</b> £%{{x:,.2f}}<br>"
                + "<b>Units Sold:</b> %{customdata[0]:,}<br>"
                + "<b>Units Returned:</b> %{customdata[1]:,}<br>"
                + "<b>Return Rate (Rev):</b> %{customdata[2]:.1f}%<extra></extra>"
            ),
        )
    )

    fig.update_layout(xaxis_title="Net Revenue (£)", yaxis_title="")
    return _apply_theme(fig, title=title, height=450)


def plot_country_choropleth(country_df: pd.DataFrame, title: str = "Global Net Revenue Distribution") -> go.Figure:
    """Choropleth world map of net revenue."""
    if country_df.empty:
        return go.Figure()

    fig = px.choropleth(
        country_df,
        locations="Country",
        locationmode="country names",
        color="net_revenue",
        hover_name="Country",
        color_continuous_scale="Blues",
        labels={"net_revenue": "Net Rev (£)"},
    )

    fig.update_layout(
        template=TEMPLATE,
        title=dict(text=f"<b>{title}</b>", x=0.01, y=0.96),
        margin=dict(l=0, r=0, t=50, b=0),
        height=450,
        geo=dict(showframe=False, showcoastlines=True, projection_type="equirectangular"),
    )
    return fig


def plot_rfm_segments_treemap(rfm_stats: Dict, title: str = "Customer Segmentation Overview (RFM)") -> go.Figure:
    """Treemap of customer segments showing headcount and monetary contribution."""
    seg_list = rfm_stats.get("segment_summary", [])
    if not seg_list:
        return go.Figure()

    df_seg = pd.DataFrame(seg_list)
    df_seg["color"] = df_seg["Segment"].map(lambda s: SEGMENT_COLORS.get(s, "#94A3B8"))

    fig = px.treemap(
        df_seg,
        path=["Segment"],
        values="total_monetary",
        color="Segment",
        color_discrete_map=SEGMENT_COLORS,
        custom_data=["customer_count", "customer_share_pct", "avg_recency", "avg_frequency"],
    )

    fig.data[0].texttemplate = (
        "<b>%{label}</b><br>Revenue: £%{value:,.0f}<br>Customers: %{customdata[0]:,} (%{customdata[1]:.1f}%)"
    )
    fig.data[0].hovertemplate = (
        "<b>Segment: %{label}</b><br>"
        + "Total Spend: £%{value:,.2f}<br>"
        + "Customer Count: %{customdata[0]:,} (%{customdata[1]:.1f}%)<br>"
        + "Avg Recency: %{customdata[2]:.1f} days<br>"
        + "Avg Frequency: %{customdata[3]:.1f} orders<extra></extra>"
    )

    fig.update_layout(
        template=TEMPLATE,
        title=dict(text=f"<b>{title}</b>", x=0.01, y=0.96),
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
    )
    return fig


def plot_rfm_scatter(rfm_df: pd.DataFrame, title: str = "Recency vs. Monetary by Segment") -> go.Figure:
    """2D scatter plot showing Recency vs Monetary spend with Frequency encoded as size."""
    if rfm_df.empty:
        return go.Figure()

    # Sample if large to maintain smooth browser responsiveness
    sample_df = rfm_df.sample(n=min(1500, len(rfm_df)), random_state=42) if len(rfm_df) > 1500 else rfm_df

    fig = px.scatter(
        sample_df,
        x="Recency",
        y="Monetary",
        size="Frequency",
        color="Segment",
        color_discrete_map=SEGMENT_COLORS,
        hover_name="CustomerID",
        log_y=True,
        labels={"Recency": "Recency (Days Since Last Purchase)", "Monetary": "Monetary Spend (£, Log Scale)"},
    )

    return _apply_theme(fig, title=title, height=450)


def plot_cohort_heatmap(cohort_pct: pd.DataFrame, title: str = "Customer Retention Rate by Monthly Cohort (%)") -> go.Figure:
    """Interactive heatmap showing monthly retention rates."""
    if cohort_pct.empty:
        return go.Figure()

    fig = go.Figure(
        data=go.Heatmap(
            z=cohort_pct.values,
            x=[f"Month {c}" for c in cohort_pct.columns],
            y=cohort_pct.index.astype(str),
            colorscale="Viridis",
            text=np.round(cohort_pct.values, 1),
            texttemplate="%{text}%",
            hoverongaps=False,
            colorbar=dict(title="Retention %"),
        )
    )

    fig.update_layout(
        xaxis_title="Months Since First Acquisition",
        yaxis_title="Cohort Acquisition Month",
        yaxis=dict(autorange="reversed"),
    )
    return _apply_theme(fig, title=title, height=450)


def plot_day_hour_heatmap(heatmap_df: pd.DataFrame, title: str = "Order Density: Day of Week vs. Hour of Day") -> go.Figure:
    """Heatmap of order volume across days of the week and hours of day."""
    if heatmap_df.empty:
        return go.Figure()

    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_df.values,
            x=[f"{h:02d}:00" for h in heatmap_df.columns],
            y=heatmap_df.index,
            colorscale="Blues",
            colorbar=dict(title="Order Count"),
            hovertemplate="<b>Day:</b> %{y}<br><b>Hour:</b> %{x}<br><b>Orders:</b> %{z:,}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title="Hour of Day",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )
    return _apply_theme(fig, title=title, height=380)


def plot_audit_funnel(audit_df: pd.DataFrame, title: str = "Data Cleaning Pipeline Audit Funnel") -> go.Figure:
    """Funnel chart displaying record count progression across cleaning stages."""
    if audit_df.empty:
        return go.Figure()

    fig = go.Figure(
        go.Funnel(
            y=audit_df["step_name"],
            x=audit_df["records_after"],
            textinfo="value+percent previous",
            marker=dict(color=COLORS["primary"]),
            customdata=np.stack(
                (audit_df["records_impacted"], audit_df["description"]), axis=-1
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                + "Remaining Records: %{x:,}<br>"
                + "Removed in Step: %{customdata[0]:,}<br>"
                + "Rule: %{customdata[1]}<extra></extra>"
            ),
        )
    )

    return _apply_theme(fig, title=title, height=400)
