"""
Sales Analysis Page
In-depth temporal trends, peak shopping patterns, weekday/hour heatmaps,
and cross-market comparisons.
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics import (
    get_country_performance,
    get_revenue_trend,
    get_sales_time_heatmap,
    get_top_products,
)
from src.visualizations import plot_day_hour_heatmap

st.set_page_config(page_title="Sales Analysis", page_icon="📈", layout="wide")

df = st.session_state.get("df_filtered")
if df is None or df.empty:
    from app import load_base_data
    df = load_base_data("full")
    st.session_state["df_filtered"] = df
    st.session_state["df_base"] = df

st.title("📈 Granular Sales & Demand Analysis")
st.markdown(
    "Explore temporal rhythms, operational peak periods, and geographic patterns across merchandise sales."
)

# 1. Daily Sales Trends & Moving Averages
st.subheader("📅 Daily Sales Trajectory & 7-Day Moving Average")

daily_trend = get_revenue_trend(df, freq="D")
if not daily_trend.empty:
    fig_daily = go.Figure()

    fig_daily.add_trace(
        go.Bar(
            x=daily_trend["period"],
            y=daily_trend["net_revenue"],
            name="Daily Net Sales",
            marker_color="#93C5FD",
            opacity=0.7,
            hovertemplate="<b>Date:</b> %{x|%d %b %Y}<br><b>Net Sales:</b> £%{y:,.2f}<extra></extra>",
        )
    )

    fig_daily.add_trace(
        go.Scatter(
            x=daily_trend["period"],
            y=daily_trend["rolling_7p_net_revenue"],
            name="7-Day Rolling Mean",
            mode="lines",
            line=dict(color="#1D4ED8", width=3),
            hovertemplate="<b>7-Day Mean:</b> £%{y:,.2f}<extra></extra>",
        )
    )

    fig_daily.update_layout(
        template="plotly_white",
        xaxis_title="Date",
        yaxis_title="Revenue (£)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=40, b=40),
        height=400,
    )
    st.plotly_chart(fig_daily, use_container_width=True)

st.markdown("---")

# 2. Operational Heatmaps: Weekday & Hour of Day Demand
st.subheader("⏰ Peak Shopping Rhythms (Day of Week vs. Hour of Day)")
st.caption("Identify peak operational windows for warehousing, logistics dispatch, and marketing campaigns.")

time_matrix = get_sales_time_heatmap(df)
if not time_matrix.empty:
    fig_heat = plot_day_hour_heatmap(time_matrix, title="Order Density Heatmap (Number of Distinct Orders)")
    st.plotly_chart(fig_heat, use_container_width=True)

    # Key insight callout
    st.info(
        """
        💡 **Operational Insight**:
        - Order activity is highest between **10:00 AM and 3:00 PM**, peaking around **12:00 PM (lunch hour)**.
        - **Thursdays and Tuesdays** consistently drive peak wholesale and retail order volumes.
        - UCI Online Retail dataset records zero orders on Saturdays (the business did not process or log weekend transactions on Saturdays).
        """
    )

st.markdown("---")

# 3. International Comparisons (Excluding or Highlighting UK)
st.subheader("🌐 Global Market Penetration")

country_df = get_country_performance(df)
intl_df = country_df[country_df["Country"] != "United Kingdom"].head(10)

col1, col2 = st.columns(2)
with col1:
    fig_intl = px.bar(
        intl_df,
        x="net_revenue",
        y="Country",
        orientation="h",
        color="net_revenue",
        color_continuous_scale="Viridis",
        title="<b>Top 10 International Markets (Excl. UK)</b>",
        labels={"net_revenue": "Net Revenue (£)", "Country": ""},
    )
    fig_intl.update_layout(
        template="plotly_white",
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
        height=400,
    )
    st.plotly_chart(fig_intl, use_container_width=True)

with col2:
    # AOV comparison across markets
    fig_aov = px.scatter(
        intl_df,
        x="total_orders",
        y="aov",
        size="net_revenue",
        color="Country",
        text="Country",
        title="<b>Average Order Value vs. Order Volume by Country</b>",
        labels={"total_orders": "Total Orders", "aov": "Average Order Value (£)"},
    )
    fig_aov.update_traces(textposition="top center")
    fig_aov.update_layout(
        template="plotly_white",
        showlegend=False,
        height=400,
    )
    st.plotly_chart(fig_aov, use_container_width=True)
