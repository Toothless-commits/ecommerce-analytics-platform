"""
E-Commerce Analytics Platform - Main Application Entrypoint
A portfolio-grade interactive analytics dashboard built with Streamlit and Plotly.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import pandas as pd
import streamlit as st

from src.config import (
    AUDIT_LOG_PATH,
    CLEANED_PARQUET_PATH,
    RAW_PARQUET_PATH,
    SAMPLE_CSV_PATH,
)
from src.data_cleaning import clean_dataset
from src.data_ingestion import load_raw_data
from src.db import check_db_connection, get_engine
from src.analytics import calculate_executive_kpis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Streamlit Page Setup
st.set_page_config(
    page_title="E-Commerce Analytics Platform",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    /* Metric Card Styling */
    .metric-card {
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 12px;
    }
    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #10B981;
        margin-top: 4px;
    }
    .metric-sub-negative {
        font-size: 0.8rem;
        color: #EF4444;
        margin-top: 4px;
    }
    /* Status Pills */
    .badge-success {
        display: inline-block;
        padding: 4px 10px;
        background-color: #DCFCE7;
        color: #166534;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-warning {
        display: inline-block;
        padding: 4px 10px;
        background-color: #FEF3C7;
        color: #92400E;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-primary {
        display: inline-block;
        padding: 4px 10px;
        background-color: #DBEAFE;
        color: #1E40AF;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    /* Section dividers */
    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1E293B;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_base_data(source_type: str = "full"):
    """
    Load data with Streamlit caching.
    Supports 'full' cleaned dataset or 'sample' demo dataset.
    """
    if source_type == "sample" and SAMPLE_CSV_PATH.exists():
        df = pd.read_csv(SAMPLE_CSV_PATH)
        df, _, _ = clean_dataset(df, save=False)
        return df

    if CLEANED_PARQUET_PATH.exists():
        df = pd.read_parquet(CLEANED_PARQUET_PATH)
        return df

    # Fallback to sample or raw load
    if SAMPLE_CSV_PATH.exists():
        df = pd.read_csv(SAMPLE_CSV_PATH)
        df, _, _ = clean_dataset(df, save=False)
        return df

    raw = load_raw_data()
    df, _, _ = clean_dataset(raw, save=True)
    return df


@st.cache_data(show_spinner=False)
def load_audit_data():
    """Load audit steps JSON log if present."""
    if AUDIT_LOG_PATH.exists():
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# Database connection check
@st.cache_data(ttl=60)
def get_db_status():
    return check_db_connection()


# Global Sidebar
def render_sidebar():
    st.sidebar.image(
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&auto=format&fit=crop&q=60",
        caption="Retail Intelligence Suite",
        use_container_width=True,
    )

    st.sidebar.title("🎛️ Analytics Controls")

    # DB Connection Status Indicator
    is_connected, db_msg = get_db_status()
    if is_connected:
        st.sidebar.markdown(
            '<div class="badge-success">🟢 PostgreSQL Connected</div>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            '<div class="badge-warning">🟡 Demo Mode (Local Parquet)</div>',
            unsafe_allow_html=True,
        )
    st.sidebar.caption(db_msg)
    st.sidebar.markdown("---")

    # Dataset Source Selector
    data_mode = st.sidebar.radio(
        "📁 Dataset Mode",
        options=["Full Dataset (~531k rows)", "Fast Demo Sample (~62k rows)", "Upload Custom File"],
        index=0 if CLEANED_PARQUET_PATH.exists() else 1,
        help="Select between the full UCI retail dataset, an instant high-fidelity sample, or an uploaded CSV/XLSX.",
    )

    df_base = None
    if data_mode == "Upload Custom File":
        uploaded = st.sidebar.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"])
        if uploaded:
            raw_uploaded = load_raw_data(uploaded)
            df_base, _, _ = clean_dataset(raw_uploaded, save=False)
            st.sidebar.success(f"Loaded {len(df_base):,} rows!")
        else:
            st.sidebar.info("Upload a file or toggle to Full/Sample dataset.")
            df_base = load_base_data("sample")
    elif "Sample" in data_mode:
        df_base = load_base_data("sample")
    else:
        df_base = load_base_data("full")

    # Date Range Filter
    min_date = pd.to_datetime(df_base["InvoiceDate"]).min().date()
    max_date = pd.to_datetime(df_base["InvoiceDate"]).max().date()

    st.sidebar.subheader("📅 Date Range")
    date_selection = st.sidebar.date_input(
        "Transaction Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_selection, (tuple, list)) and len(date_selection) == 2:
        start_date, end_date = date_selection
    else:
        start_date, end_date = min_date, max_date

    # Country Filter
    countries = ["All Countries"] + sorted(df_base["Country"].dropna().unique().tolist())
    selected_country = st.sidebar.selectbox("🌍 Country", options=countries, index=0)

    # Customer Type Filter
    customer_type = st.sidebar.radio(
        "👤 Customer Type",
        options=["All Customers", "Identified Only (Registered)", "Guest Only (Unregistered)"],
        index=0,
    )

    # Order Status Filter
    order_status = st.sidebar.selectbox(
        "📦 Order Status",
        options=["All Transactions", "Completed Purchases Only", "Cancellations / Returns Only"],
        index=0,
    )

    # Apply Filters
    df_filtered = df_base.copy()

    # 1. Date filter
    df_filtered["InvoiceDateOnly"] = pd.to_datetime(df_filtered["InvoiceDate"]).dt.date
    df_filtered = df_filtered[
        (df_filtered["InvoiceDateOnly"] >= start_date) & (df_filtered["InvoiceDateOnly"] <= end_date)
    ]

    # 2. Country filter
    if selected_country != "All Countries":
        df_filtered = df_filtered[df_filtered["Country"] == selected_country]

    # 3. Customer Type filter
    if customer_type == "Identified Only (Registered)":
        df_filtered = df_filtered[~df_filtered["is_guest"] & df_filtered["CustomerID"].notna()]
    elif customer_type == "Guest Only (Unregistered)":
        df_filtered = df_filtered[df_filtered["is_guest"]]

    # 4. Order Status filter
    if order_status == "Completed Purchases Only":
        df_filtered = df_filtered[~df_filtered["is_cancelled"] & (df_filtered["Quantity"] > 0)]
    elif order_status == "Cancellations / Returns Only":
        df_filtered = df_filtered[df_filtered["is_cancelled"] | (df_filtered["Quantity"] < 0)]

    # Store in session_state for access across pages
    st.session_state["df_filtered"] = df_filtered
    st.session_state["df_base"] = df_base
    st.session_state["selected_country"] = selected_country
    st.session_state["start_date"] = start_date
    st.session_state["end_date"] = end_date
    st.session_state["data_mode"] = data_mode

    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"**Active Records:** {len(df_filtered):,} / {len(df_base):,} ({len(df_filtered)/len(df_base)*100:.1f}%)"
    )
    return df_filtered, df_base


def main():
    df_filtered, df_base = render_sidebar()

    st.title("🛍️ E-Commerce Analytics Platform")
    st.markdown(
        """
        Welcome to the **End-to-End E-Commerce Analytics Platform**.
        This platform delivers production-grade business intelligence, cohort retention analysis,
        and customer segmentation on real-world retail transactions from the **UCI Online Retail Dataset**.
        """
    )

    # Quick KPI Banner
    kpis = calculate_executive_kpis(df_filtered)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Net Revenue</div>
                <div class="metric-value">£{kpis['net_revenue']:,.2f}</div>
                <div class="metric-sub">Gross: £{kpis['gross_revenue']:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Refunds & Returns</div>
                <div class="metric-value">£{kpis['returns_revenue']:,.2f}</div>
                <div class="metric-sub-negative">{kpis['return_rate_pct']:.1f}% Return Rate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Purchase Orders</div>
                <div class="metric-value">{kpis['purchase_orders']:,}</div>
                <div class="metric-sub">Avg Items: {kpis['avg_items_per_order']:.1f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Identified Customers</div>
                <div class="metric-value">{kpis['unique_customers']:,}</div>
                <div class="metric-sub">Guest Orders: {kpis['guest_invoices']:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Average Order Value</div>
                <div class="metric-value">£{kpis['gross_aov']:,.2f}</div>
                <div class="metric-sub">Net AOV: £{kpis['net_aov']:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Platform Navigation Guide
    st.subheader("🧭 Dashboard Pages & Analytical Capabilities")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            """
            ### 1. 📊 Executive Overview
            - High-level commercial KPIs, revenue trajectory, and period-over-period growth rates.
            - Product Pareto distribution and country revenue shares.
            - Gross vs. Net sales reconciliation.

            ### 2. 📈 Sales Analysis
            - Granular sales trends across daily, weekly, and monthly time horizons.
            - Peak shopping hours and weekday demand heatmaps.
            - Global choropleth map and international comparison (UK vs. Europe & RoW).

            ### 3. 👥 Customer Analytics
            - **RFM Segmentation Engine**: Recency, Frequency, and Monetary scoring into 5 quintiles.
            - Segment categorization: *Champions, Loyal Customers, At Risk, Can't Lose Them, Lost*.
            - **Customer Cohort Retention Matrix**: Monthly repeat engagement tracking.
            """
        )
    with col_b:
        st.markdown(
            """
            ### 4. 📦 Product & Returns Analysis
            - Product catalog performance: Best-sellers vs. underperformers.
            - Return rate analysis by SKU and country.
            - Price distribution and quantity elasticity.

            ### 5. 🔍 Data Quality & Auditing
            - Complete step-by-step cleaning audit trail (duplicates, zero prices, admin codes).
            - Unidentified Customer (guest checkout) impact assessment.
            - **Direct SQL Terminal**: Run and inspect live PostgreSQL queries with CTEs and Window Functions.
            """
        )

    # Metric Accounting Callout
    st.info(
        """
        ℹ️ **Portfolio Note on Metric Integrity**:
        - **Gross Sales** accounts for valid sales lines (`Quantity > 0` and `UnitPrice > 0`).
        - **Returns & Cancellations** are explicitly isolated (`is_cancelled = True` or `Quantity < 0`).
        - **Guest Checkouts** (~25% of dataset) are preserved for revenue calculations while customer-centric RFM and cohort metrics isolate identifiable accounts.
        - **Zero fabricated figures**: All numbers update dynamically from the cleaned transaction data.
        """
    )


if __name__ == "__main__":
    main()
