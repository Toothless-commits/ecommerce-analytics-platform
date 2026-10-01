"""
Customer Analytics Page
Provides RFM customer segmentation, cohort retention tracking,
and customer lifetime value distributions.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics import calculate_cohort_retention, calculate_rfm
from src.visualizations import (
    plot_cohort_heatmap,
    plot_rfm_scatter,
    plot_rfm_segments_treemap,
)

st.set_page_config(page_title="Customer Analytics", page_icon="👥", layout="wide")

df = st.session_state.get("df_filtered")
if df is None or df.empty:
    from app import load_base_data
    df = load_base_data("full")
    st.session_state["df_filtered"] = df
    st.session_state["df_base"] = df

st.title("👥 Customer Intelligence & Behavioral Segmentation")
st.markdown(
    """
    Leverage **RFM (Recency, Frequency, Monetary)** behavioral modeling and **Monthly Cohort Retention**
    to uncover high-value customer segments, identify churn risks, and measure customer lifetime value.
    """
)

# 1. Customer Retention & Repeat Purchase Rate
rfm_df, rfm_stats = calculate_rfm(df)

if rfm_df.empty:
    st.info("No identifiable customer accounts found in current filter selection (e.g., Guest Checkouts selected).")
    st.stop()

# Key Customer Metrics
total_custs = len(rfm_df)
repeat_custs = (rfm_df["Frequency"] >= 2).sum()
repeat_rate = (repeat_custs / total_custs * 100.0) if total_custs > 0 else 0.0
avg_orders = rfm_df["Frequency"].mean()
avg_clv = rfm_df["Monetary"].mean()
median_clv = rfm_df["Monetary"].median()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        label="Identified Accounts Analyzed",
        value=f"{total_custs:,}",
        help="Customers with positive net commercial orders.",
    )
with c2:
    st.metric(
        label="Repeat Purchase Rate",
        value=f"{repeat_rate:.1f}%",
        delta=f"{repeat_custs:,} repeat buyers",
        help="Percentage of identified customers who placed 2 or more orders.",
    )
with c3:
    st.metric(
        label="Average Orders per Customer",
        value=f"{avg_orders:.2f}",
        help="Mean distinct purchase invoices per customer.",
    )
with c4:
    st.metric(
        label="Average Customer Value (CLV)",
        value=f"£{avg_clv:,.2f}",
        delta=f"Median £{median_clv:,.2f}",
        help="Mean lifetime spend per identified customer.",
    )

st.markdown("---")

# 2. RFM Methodology & Segment Breakdown
st.subheader("🎯 RFM Customer Segmentation Matrix")

with st.expander("📖 Methodology: How RFM Scores are Derived", expanded=False):
    st.markdown(
        """
        **Recency (R)**: Days elapsed since the customer's last purchase relative to the dataset boundary.
        - Quintile 5: Most recent (Top 20%)
        - Quintile 1: Least recent (Bottom 20%)

        **Frequency (F)**: Total number of distinct commercial purchase invoices.
        - Quintile 5: Most frequent transactions
        - Quintile 1: Single purchase / least frequent

        **Monetary (M)**: Net cumulative revenue generated across all valid transactions.
        - Quintile 5: Highest lifetime expenditure
        - Quintile 1: Lowest lifetime expenditure

        **Composite Score**: Concatenation `[R][F][M]` mapped into 9 strategic customer personas:
        *Champions*, *Loyal Customers*, *New / Potential Loyalists*, *Promising*, *At Risk*, *Can't Lose Them*, *About to Sleep*, *Hibernating*, and *Lost Customers*.
        """
    )

tab_treemap, tab_scatter, tab_table = st.tabs(["🌳 Segment Treemap", "🌌 2D/3D Behavioral Scatter", "📋 Segment Strategy Matrix"])

with tab_treemap:
    fig_tree = plot_rfm_segments_treemap(rfm_stats, title="Customer Share vs. Revenue Contribution by Segment")
    st.plotly_chart(fig_tree, use_container_width=True)

with tab_scatter:
    fig_scat = plot_rfm_scatter(rfm_df, title="Customer Spend vs. Recency (Bubble Size = Frequency)")
    st.plotly_chart(fig_scat, use_container_width=True)

with tab_table:
    summary_data = rfm_stats.get("segment_summary", [])
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        # Business Action Strategies
        strategies = {
            "Champions": "Reward loyalty, provide VIP early access to new collections, solicit reviews.",
            "Loyal Customers": "Upsell higher-value items, cross-sell related categories, offer membership tiers.",
            "New / Potential Loyalists": "Onboarding email sequences, incentives for second purchase within 30 days.",
            "Promising / Regular": "Personalized recommendations based on past SKU choices, limited-time promotions.",
            "At Risk (High Spenders)": "Urgent reactivation campaigns, personalized outreach, survey on experience.",
            "Can't Lose Them": "High-touch win-back offers, direct relationship management, renewed discount codes.",
            "About to Sleep": "Share popular trending items, remind of reward balance before expiry.",
            "Hibernating": "Low-cost automated re-engagement series, offer steep clearance discounts.",
            "Lost Customers": "Occasional brand awareness campaigns or prune from expensive ad targeting.",
        }
        df_summary["Recommended Action"] = df_summary["Segment"].map(lambda s: strategies.get(s, "Standard engagement"))

        st.dataframe(
            df_summary.rename(
                columns={
                    "customer_count": "Customers",
                    "customer_share_pct": "Customer Share (%)",
                    "total_monetary": "Total Spend (£)",
                    "monetary_share_pct": "Spend Share (%)",
                    "avg_recency": "Avg Recency (Days)",
                    "avg_frequency": "Avg Orders",
                    "avg_monetary": "Avg Spend (£)",
                }
            ).style.format(
                {
                    "Customers": "{:,}",
                    "Customer Share (%)": "{:.1f}%",
                    "Total Spend (£)": "£{:,.2f}",
                    "Spend Share (%)": "{:.1f}%",
                    "Avg Recency (Days)": "{:.1f}",
                    "Avg Orders": "{:.1f}",
                    "Avg Spend (£)": "£{:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

st.markdown("---")

# 3. Customer Acquisition Cohort Retention
st.subheader("📅 Monthly Cohort Retention Analysis")
st.caption("Tracks repeat transaction rates for cohorts defined by their first purchase month.")

cohort_pct, cohort_counts = calculate_cohort_retention(df)
if not cohort_pct.empty:
    fig_cohort = plot_cohort_heatmap(cohort_pct, title="Cohort Retention Rates Across 12 Months (%)")
    st.plotly_chart(fig_cohort, use_container_width=True)

    with st.expander("📊 View Raw Customer Retention Headcounts", expanded=False):
        st.dataframe(cohort_counts.fillna(0).astype(int), use_container_width=True)
