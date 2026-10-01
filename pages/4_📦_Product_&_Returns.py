"""
Product & Returns Analysis Page
Explores merchandise sales, return rates by SKU, net vs gross margins,
and refund value concentrations.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics import get_top_products

st.set_page_config(page_title="Product & Returns", page_icon="📦", layout="wide")

df = st.session_state.get("df_filtered")
if df is None or df.empty:
    from app import load_base_data
    df = load_base_data("full")
    st.session_state["df_filtered"] = df
    st.session_state["df_base"] = df

st.title("📦 Product Performance & Returns Analysis")
st.markdown(
    """
    Examine product-level gross revenue, cancellation and return patterns,
    refund rates, and quantity distributions across the merchandise catalog.
    """
)

# 1. High-Level Product & Returns Summary
sales_rows = df[~df["is_cancelled"] & (df["Quantity"] > 0)]
return_rows = df[df["is_cancelled"] | (df["Quantity"] < 0)]

total_gross = sales_rows["LineTotal"].sum()
total_refund = return_rows["LineTotal"].abs().sum()
overall_return_rate = (total_refund / total_gross * 100.0) if total_gross > 0 else 0.0

total_units_sold = sales_rows["Quantity"].sum()
total_units_returned = return_rows["Quantity"].abs().sum()
unit_return_rate = (
    total_units_returned / (total_units_sold + total_units_returned) * 100.0
    if (total_units_sold + total_units_returned) > 0
    else 0.0
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total Catalog SKUs", f"{df['StockCode'].nunique():,}")
with c2:
    st.metric("Gross Product Sales", f"£{total_gross:,.2f}")
with c3:
    st.metric(
        "Refunded Product Value",
        f"£{total_refund:,.2f}",
        delta=f"-{overall_return_rate:.2f}% Revenue Return Rate",
        delta_color="inverse",
    )
with c4:
    st.metric(
        "Units Returned",
        f"{total_units_returned:,}",
        delta=f"-{unit_return_rate:.2f}% Unit Return Rate",
        delta_color="inverse",
    )

st.markdown("---")

# 2. Product Explorer: Net Revenue vs. Return Rate
st.subheader("📊 Product Catalog Performance Table")

col_filter, col_sort = st.columns([2, 2])
with col_filter:
    min_units = st.slider("Minimum Units Sold Filter", min_value=10, max_value=2000, value=100, step=50)
with col_sort:
    sort_criterion = st.selectbox(
        "Sort Products By",
        options=["Net Revenue", "Units Sold", "Refund Amount", "Return Rate (Revenue %)"],
        index=0,
    )

sort_map = {
    "Net Revenue": "net_revenue",
    "Units Sold": "units_sold",
    "Refund Amount": "refund_amount",
    "Return Rate (Revenue %)": "return_rate_rev_pct",
}

all_prods = get_top_products(df, top_n=200, sort_by=sort_map[sort_criterion])
filtered_prods = all_prods[all_prods["units_sold"] >= min_units]

# Top 15 visual comparison: Gross vs Net vs Returns
top_15 = filtered_prods.head(15).copy()
if not top_15.empty:
    fig_bar = go.Figure()
    fig_bar.add_trace(
        go.Bar(
            name="Net Revenue (£)",
            x=top_15["StockCode"],
            y=top_15["net_revenue"],
            marker_color="#2563EB",
            hovertext=top_15["description"],
            hovertemplate="<b>SKU: %{x}</b><br>%{hovertext}<br>Net Revenue: £%{y:,.2f}<extra></extra>",
        )
    )
    fig_bar.add_trace(
        go.Bar(
            name="Refund Amount (£)",
            x=top_15["StockCode"],
            y=top_15["refund_amount"],
            marker_color="#EF4444",
            hovertext=top_15["description"],
            hovertemplate="<b>SKU: %{x}</b><br>%{hovertext}<br>Refunds: £%{y:,.2f}<extra></extra>",
        )
    )
    fig_bar.update_layout(
        template="plotly_white",
        title=dict(text="<b>Top Products: Net Sales vs. Refunds (£)</b>", x=0.01),
        barmode="stack",
        xaxis_title="Stock Code",
        yaxis_title="Value (£)",
        height=420,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# Data Table
st.dataframe(
    filtered_prods.rename(
        columns={
            "description": "Product Description",
            "units_sold": "Units Sold",
            "units_returned": "Units Returned",
            "gross_sales": "Gross Sales (£)",
            "refund_amount": "Refund Amount (£)",
            "net_revenue": "Net Revenue (£)",
            "order_count": "Orders",
            "return_rate_rev_pct": "Return Rate (Rev %)",
        }
    ).style.format(
        {
            "Units Sold": "{:,}",
            "Units Returned": "{:,}",
            "Gross Sales (£)": "£{:,.2f}",
            "Refund Amount (£)": "£{:,.2f}",
            "Net Revenue (£)": "£{:,.2f}",
            "Orders": "{:,}",
            "Return Rate (Rev %)": "{:.2f}%",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")

# 3. Unit Price & Quantity Distributions (Outlier & Wholesale Detection)
st.subheader("📈 Order Quantity & Price Distributions")

col_p1, col_p2 = st.columns(2)
with col_p1:
    fig_qty = px.histogram(
        sales_rows[sales_rows["Quantity"] <= 100],
        x="Quantity",
        nbins=50,
        title="<b>Sales Quantity Distribution (Orders <= 100 units)</b>",
        color_discrete_sequence=["#3B82F6"],
        labels={"Quantity": "Units per Line Item"},
    )
    fig_qty.update_layout(template="plotly_white", height=350)
    st.plotly_chart(fig_qty, use_container_width=True)

with col_p2:
    fig_pr = px.histogram(
        sales_rows[sales_rows["UnitPrice"] <= 20],
        x="UnitPrice",
        nbins=40,
        title="<b>Unit Price Distribution (Items <= £20)</b>",
        color_discrete_sequence=["#10B981"],
        labels={"UnitPrice": "Unit Price (£)"},
    )
    fig_pr.update_layout(template="plotly_white", height=350)
    st.plotly_chart(fig_pr, use_container_width=True)
