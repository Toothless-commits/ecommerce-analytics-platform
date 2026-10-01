"""
Data Quality & Audit Page
Full transparency on cleaning rules, duplicate handling, missing values,
and an interactive SQL console demonstrating CTEs and Window Functions.
"""

import time
import pandas as pd
import streamlit as st
from sqlalchemy import text

from src.config import AUDIT_LOG_PATH
from src.db import check_db_connection, execute_query, get_engine
from src.sql_analytics import (
    run_integrity_check_sql,
    run_mom_growth_query,
    run_rfm_sql_query,
    run_top_products_sql_query,
)
from src.visualizations import plot_audit_funnel

st.set_page_config(page_title="Data Quality & SQL", page_icon="🔍", layout="wide")

st.title("🔍 Data Quality, Cleansing Audit & SQL Intelligence")
st.markdown(
    """
    Every analytical conclusion requires data integrity.
    This page details every transformation applied to the raw UCI dataset,
    quantifies the impact of guest checkouts, and provides an interactive SQL terminal
    to inspect PostgreSQL analytical queries directly.
    """
)

tab_audit, tab_missing, tab_sql = st.tabs(
    ["🧹 Data Cleansing Audit Trail", "👤 Missing Values & Guest Impact", "💻 Interactive SQL Console"]
)

# 1. Audit Trail Tab
with tab_audit:
    st.subheader("📋 Step-by-Step Cleansing Funnel")

    import json
    if AUDIT_LOG_PATH.exists():
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            audit_data = json.load(f)
        steps = audit_data.get("steps", [])
        stats = audit_data.get("summary", {})
        df_audit = pd.DataFrame(steps)
    else:
        df_audit = pd.DataFrame()
        stats = {}

    if not df_audit.empty:
        fig_funnel = plot_audit_funnel(df_audit, title="Data Retention Funnel Through Cleaning Steps")
        st.plotly_chart(fig_funnel, use_container_width=True)

        st.markdown("### Transformation Rules Log")
        st.dataframe(
            df_audit.rename(
                columns={
                    "step_name": "Stage ID",
                    "description": "Rule Description",
                    "records_before": "Records Before",
                    "records_after": "Records After",
                    "records_impacted": "Records Filtered",
                    "pct_impacted": "Impact (%)",
                    "notes": "Accounting Rationale",
                }
            ).style.format(
                {
                    "Records Before": "{:,}",
                    "Records After": "{:,}",
                    "Records Filtered": "{:,}",
                    "Impact (%)": "{:.3f}%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.info(
            f"""
            **Dataset Summary**:
            - **Raw Ingested Records**: {stats.get('raw_total_records', 0):,}
            - **Cleaned Commercial Records**: {stats.get('cleaned_total_records', 0):,} (**{stats.get('retention_rate_pct', 0)}% retention**)
            - **Exact Duplicates Removed**: {df_audit.loc[df_audit['step_name']=='2_EXACT_DUPLICATES', 'records_impacted'].sum():,}
            - **Zero/Negative Price Records Removed**: {df_audit.loc[df_audit['step_name']=='3_INVALID_PRICE', 'records_impacted'].sum():,} (inventory write-offs, lost items)
            - **Administrative Codes Filtered**: {df_audit.loc[df_audit['step_name']=='5_ADMIN_STOCK_CODES', 'records_impacted'].sum():,} (Postage, Discounts, Bank charges)
            """
        )

# 2. Missing CustomerID Tab
with tab_missing:
    st.subheader("👤 Analysis of Unidentified Customers (Guest Checkouts)")
    st.markdown(
        """
        In the raw UCI dataset, **135,080 rows (~24.9%)** lack a registered `CustomerID`.
        A common rookie mistake is dropping these rows entirely, which artificially deflates revenue and orders by ~25%.
        """
    )

    df_active = st.session_state.get("df_filtered")
    if df_active is not None and not df_active.empty:
        guest_summary = df_active.groupby("is_guest").agg(
            rows=("InvoiceNo", "count"),
            invoices=("InvoiceNo", "nunique"),
            net_revenue=("LineTotal", "sum"),
        ).reset_index()

        total_r = guest_summary["rows"].sum()
        total_rev = guest_summary["net_revenue"].sum()

        guest_summary["row_pct"] = (guest_summary["rows"] / total_r * 100).round(2)
        guest_summary["rev_pct"] = (guest_summary["net_revenue"] / total_rev * 100).round(2)
        guest_summary["label"] = guest_summary["is_guest"].map(
            {True: "Guest Checkout (Unregistered)", False: "Identified Customer (Registered)"}
        )

        st.dataframe(
            guest_summary[["label", "rows", "row_pct", "invoices", "net_revenue", "rev_pct"]].rename(
                columns={
                    "label": "Customer Classification",
                    "rows": "Line Items",
                    "row_pct": "Share of Rows (%)",
                    "invoices": "Distinct Orders",
                    "net_revenue": "Net Revenue (£)",
                    "rev_pct": "Share of Revenue (%)",
                }
            ).style.format(
                {
                    "Line Items": "{:,}",
                    "Share of Rows (%)": "{:.2f}%",
                    "Distinct Orders": "{:,}",
                    "Net Revenue (£)": "£{:,.2f}",
                    "Share of Revenue (%)": "{:.2f}%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.success(
        """
        **Architectural Decision**:
        1. **Preserved for Financial Reporting**: All valid guest transactions are maintained in the primary sales fact table to guarantee 100% financial accuracy for revenue, order volume, and unit sales.
        2. **Excluded from Customer Cohorts & RFM**: Customer-centric metrics require persistent user identifiers to compute recency and frequency across multiple visits. Unregistered checkouts are tagged with `is_guest = True` and isolated from RFM.
        """
    )

# 3. Interactive SQL Console Tab
with tab_sql:
    st.subheader("💻 PostgreSQL Analytical Query Console")
    is_connected, db_msg = check_db_connection()

    if not is_connected:
        st.warning(f"⚠️ {db_msg}. Connect to PostgreSQL to run live SQL queries.")
    else:
        st.markdown(
            """
            Execute production SQL queries showcasing **Common Table Expressions (CTEs)**,
            **Window Functions (`LAG`, `NTILE`)**, and **Conditional Aggregations**.
            """
        )

        query_choice = st.selectbox(
            "Select Pre-Built Portfolio Query",
            options=[
                "1. Month-over-Month Revenue & Order Growth (CTEs + LAG())",
                "2. Customer RFM Quintile Scoring (CTEs + NTILE(5) OVER())",
                "3. Top Products with Return Rate & Net Revenue",
                "4. Database Data Integrity & Arithmetic Reconciliation",
                "5. Write Custom SQL Query",
            ],
        )

        sql_code = ""
        if "1. Month-over-Month" in query_choice:
            sql_code = """WITH monthly_metrics AS (
    SELECT
        year_month,
        COUNT(DISTINCT CASE WHEN NOT is_cancelled THEN invoice_no END) AS purchase_orders,
        COUNT(DISTINCT customer_id) AS active_customers,
        SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END) AS gross_revenue,
        SUM(CASE WHEN is_cancelled THEN ABS(line_total) ELSE 0 END) AS return_amount,
        SUM(line_total) AS net_revenue
    FROM cleaned_transactions
    GROUP BY year_month
),
mom_growth AS (
    SELECT
        year_month,
        purchase_orders,
        active_customers,
        gross_revenue,
        return_amount,
        net_revenue,
        LAG(net_revenue, 1) OVER (ORDER BY year_month) AS prev_month_net_revenue,
        LAG(purchase_orders, 1) OVER (ORDER BY year_month) AS prev_month_orders
    FROM monthly_metrics
)
SELECT
    year_month,
    purchase_orders,
    active_customers,
    ROUND(gross_revenue, 2) AS gross_revenue,
    ROUND(return_amount, 2) AS return_amount,
    ROUND(net_revenue, 2) AS net_revenue,
    ROUND(
        CASE
            WHEN prev_month_net_revenue IS NULL OR prev_month_net_revenue = 0 THEN 0.0
            ELSE ((net_revenue - prev_month_net_revenue) / prev_month_net_revenue) * 100.0
        END, 2
    ) AS mom_net_revenue_growth_pct
FROM mom_growth
ORDER BY year_month;"""

        elif "2. Customer RFM" in query_choice:
            sql_code = """WITH reference_date AS (
    SELECT MAX(invoice_date) + INTERVAL '1 day' AS max_date
    FROM cleaned_transactions
),
customer_summary AS (
    SELECT
        t.customer_id,
        MIN(t.invoice_date) AS first_purchase_date,
        MAX(t.invoice_date) AS last_purchase_date,
        DATE_PART('day', (SELECT max_date FROM reference_date) - MAX(t.invoice_date))::INT AS recency_days,
        COUNT(DISTINCT CASE WHEN NOT t.is_cancelled THEN t.invoice_no END) AS frequency_orders,
        SUM(t.line_total) AS monetary_spend
    FROM cleaned_transactions t
    WHERE NOT t.is_guest AND t.customer_id IS NOT NULL
    GROUP BY t.customer_id
    HAVING SUM(t.line_total) > 0 AND COUNT(DISTINCT CASE WHEN NOT t.is_cancelled THEN t.invoice_no END) > 0
),
rfm_scores AS (
    SELECT
        customer_id,
        recency_days,
        frequency_orders,
        ROUND(monetary_spend, 2) AS monetary_spend,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency_orders ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary_spend ASC) AS m_score
    FROM customer_summary
)
SELECT
    customer_id,
    recency_days,
    frequency_orders,
    monetary_spend,
    CONCAT(r_score, f_score, m_score) AS rfm_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Potential Loyalists'
        WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'At Risk (High Value)'
        WHEN r_score = 1 AND f_score = 1 THEN 'Lost'
        ELSE 'Needs Attention / Regular'
    END AS segment_label
FROM rfm_scores
ORDER BY monetary_spend DESC
LIMIT 25;"""

        elif "3. Top Products" in query_choice:
            sql_code = """SELECT
    stock_code,
    MAX(description) AS product_name,
    SUM(CASE WHEN NOT is_cancelled THEN quantity ELSE 0 END) AS units_sold,
    SUM(CASE WHEN is_cancelled THEN ABS(quantity) ELSE 0 END) AS units_returned,
    ROUND(SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END), 2) AS gross_sales,
    ROUND(SUM(CASE WHEN is_cancelled THEN ABS(line_total) ELSE 0 END), 2) AS refund_value,
    ROUND(SUM(line_total), 2) AS net_revenue,
    ROUND(
        CASE
            WHEN SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END) = 0 THEN 0.0
            ELSE (SUM(CASE WHEN is_cancelled THEN ABS(line_total) ELSE 0 END) /
                  SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END)) * 100.0
        END, 2
    ) AS return_rate_revenue_pct
FROM cleaned_transactions
WHERE stock_code NOT IN ('POST', 'D', 'M', 'C2', 'BANK CHARGES')
GROUP BY stock_code
HAVING SUM(CASE WHEN NOT is_cancelled THEN quantity ELSE 0 END) > 50
ORDER BY net_revenue DESC
LIMIT 15;"""

        elif "4. Database Data Integrity" in query_choice:
            sql_code = """SELECT
    ROUND(SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END), 2) AS gross_sales,
    ROUND(SUM(CASE WHEN is_cancelled THEN ABS(line_total) ELSE 0 END), 2) AS returned_value,
    ROUND(SUM(line_total), 2) AS net_revenue,
    ROUND(
        SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END) -
        SUM(CASE WHEN is_cancelled THEN ABS(line_total) ELSE 0 END) -
        SUM(line_total), 4
    ) AS arithmetic_discrepancy
FROM cleaned_transactions;"""

        # Query text area
        query_input = st.text_area("SQL Statement (Read-Only)", value=sql_code, height=260)

        if st.button("🚀 Execute Query", type="primary"):
            # Check read-only safety
            forbidden = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"]
            if any(cmd in query_input.upper() for cmd in forbidden):
                st.error("❌ Destructive SQL commands are disabled in the web console.")
            else:
                try:
                    t0 = time.time()
                    res_df = execute_query(query_input)
                    dur = (time.time() - t0) * 1000
                    st.success(f"Query returned {len(res_df):,} rows in {dur:.1f} ms")
                    st.dataframe(res_df, use_container_width=True)
                except Exception as e:
                    st.error(f"SQL Execution Error: {e}")
