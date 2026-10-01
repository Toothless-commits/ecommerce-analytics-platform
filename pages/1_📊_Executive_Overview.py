"""
Executive Overview Page
Presents high-level business KPIs, revenue trajectories, MoM growth,
and key country and product drivers.
"""

import pandas as pd
import streamlit as st

from src.analytics import (
    calculate_executive_kpis,
    get_country_performance,
    get_revenue_trend,
    get_top_products,
)
from src.visualizations import (
    plot_country_choropleth,
    plot_revenue_trend,
    plot_top_products,
)

st.set_page_config(page_title="Executive Overview", page_icon="📊", layout="wide")

# Check filtered data in session state or fallback
df = st.session_state.get("df_filtered")
if df is None or df.empty:
    from app import load_base_data
    df = load_base_data("full")
    st.session_state["df_filtered"] = df
    st.session_state["df_base"] = df

st.title("📊 Executive Commercial Overview")
st.caption(
    f"Analyzing **{len(df):,} transactions** from **{df['InvoiceDate'].min().strftime('%d %b %Y')}** to **{df['InvoiceDate'].max().strftime('%d %b %Y')}**"
)

# 1. Executive KPI Summary Cards
kpis = calculate_executive_kpis(df)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric(
        label="Net Realized Revenue",
        value=f"£{kpis['net_revenue']:,.2f}",
        delta=f"Gross £{kpis['gross_revenue']:,.0f}",
        help="Gross sales minus returns and cancellations.",
    )
with col2:
    st.metric(
        label="Refunds & Returns",
        value=f"£{kpis['returns_revenue']:,.2f}",
        delta=f"-{kpis['return_rate_pct']:.1f}% rate",
        delta_color="inverse",
        help="Total monetary value refunded to customers.",
    )
with col3:
    st.metric(
        label="Purchase Orders",
        value=f"{kpis['purchase_orders']:,}",
        delta=f"{kpis['cancellation_orders']:,} returns",
        help="Unique commercial purchase invoices (excluding cancellations).",
    )
with col4:
    st.metric(
        label="Identified Customers",
        value=f"{kpis['unique_customers']:,}",
        delta=f"{kpis['guest_invoices']:,} guest orders",
        help="Distinct registered customer accounts.",
    )
with col5:
    st.metric(
        label="Average Order Value (AOV)",
        value=f"£{kpis['gross_aov']:,.2f}",
        delta=f"Net £{kpis['net_aov']:,.2f}",
        help="Gross Sales divided by Purchase Orders.",
    )

st.markdown("---")

# 2. Revenue Trajectory and Granularity Controls
st.subheader("📈 Revenue Trajectory & Order Dynamics")
granularity_col, _ = st.columns([2, 4])
with granularity_col:
    freq_choice = st.radio(
        "Time Aggregation Granularity",
        options=["Monthly", "Weekly", "Daily"],
        horizontal=True,
        index=0,
    )

freq_map = {"Monthly": "M", "Weekly": "W", "Daily": "D"}
trend_df = get_revenue_trend(df, freq=freq_map[freq_choice])

fig_trend = plot_revenue_trend(
    trend_df, title=f"{freq_choice} Revenue & Return Dynamics (£)"
)
st.plotly_chart(fig_trend, use_container_width=True)

# MoM Growth Highlights
if not trend_df.empty and len(trend_df) > 1:
    with st.expander("🔍 View Period-over-Period Performance Table", expanded=False):
        display_trend = trend_df.copy()
        display_trend["period"] = display_trend["period"].dt.strftime("%Y-%m-%d")
        display_trend = display_trend.rename(
            columns={
                "period": "Period",
                "gross_revenue": "Gross Sales (£)",
                "refund_amount": "Refunds (£)",
                "net_revenue": "Net Revenue (£)",
                "orders": "Orders",
                "customers": "Active Customers",
                "aov": "AOV (£)",
                "mom_net_growth_pct": "Net Rev Growth (%)",
            }
        )
        st.dataframe(
            display_trend[
                [
                    "Period",
                    "Net Revenue (£)",
                    "Gross Sales (£)",
                    "Refunds (£)",
                    "Orders",
                    "AOV (£)",
                    "Net Rev Growth (%)",
                ]
            ].style.format(
                {
                    "Net Revenue (£)": "£{:,.2f}",
                    "Gross Sales (£)": "£{:,.2f}",
                    "Refunds (£)": "£{:,.2f}",
                    "Orders": "{:,}",
                    "AOV (£)": "£{:,.2f}",
                    "Net Rev Growth (%)": "{:+.2f}%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

st.markdown("---")

# 3. Top Products and Geographic Revenue Drivers
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏆 Top Products by Net Revenue")
    top_products_df = get_top_products(df, top_n=10, sort_by="net_revenue")
    fig_prod = plot_top_products(top_products_df, metric="net_revenue", title="Top 10 SKUs by Net Revenue")
    st.plotly_chart(fig_prod, use_container_width=True)

with col_right:
    st.subheader("🌍 Country Revenue Contribution")
    country_df = get_country_performance(df)

    # Calculate UK vs International
    uk_row = country_df[country_df["Country"] == "United Kingdom"]
    uk_rev = uk_row["net_revenue"].iloc[0] if not uk_row.empty else 0.0
    total_rev = country_df["net_revenue"].sum()
    uk_pct = (uk_rev / total_rev * 100.0) if total_rev > 0 else 0.0

    st.markdown(
        f"""
        **United Kingdom Market Concentration**:
        - **UK Revenue**: £{uk_rev:,.2f} (**{uk_pct:.1f}%** of total net sales)
        - **International Markets**: £{(total_rev - uk_rev):,.2f} (**{100 - uk_pct:.1f}%**)
        """
    )
    fig_map = plot_country_choropleth(country_df, title="Global Net Sales Choropleth")
    st.plotly_chart(fig_map, use_container_width=True)

# Country Summary Table
with st.expander("📋 Detailed Country Performance Table", expanded=False):
    st.dataframe(
        country_df.style.format(
            {
                "total_orders": "{:,}",
                "unique_customers": "{:,}",
                "gross_revenue": "£{:,.2f}",
                "refund_amount": "£{:,.2f}",
                "net_revenue": "£{:,.2f}",
                "revenue_share_pct": "{:.2f}%",
                "aov": "£{:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
