"""
SQL Analytics module.
Executes advanced SQL queries (CTEs, Window Functions, Retention)
against PostgreSQL via SQLAlchemy, with automated fallback logic for demo mode.
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import text

from src.db import check_db_connection, execute_query, get_engine

logger = logging.getLogger(__name__)


def run_mom_growth_query(engine=None) -> pd.DataFrame:
    """Execute Month-over-Month Revenue Growth analytical query."""
    query = """
    WITH monthly_metrics AS (
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
        ) AS mom_net_revenue_growth_pct,
        ROUND(
            CASE
                WHEN prev_month_orders IS NULL OR prev_month_orders = 0 THEN 0.0
                ELSE ((purchase_orders - prev_month_orders)::NUMERIC / prev_month_orders) * 100.0
            END, 2
        ) AS mom_order_growth_pct
    FROM mom_growth
    ORDER BY year_month;
    """
    return execute_query(query, engine=engine)


def run_rfm_sql_query(limit: int = 50, engine=None) -> pd.DataFrame:
    """Execute RFM segmentation and scoring directly via SQL NTILE window functions."""
    query = f"""
    WITH reference_date AS (
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
            first_purchase_date,
            last_purchase_date,
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
        r_score,
        f_score,
        m_score,
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
    LIMIT {limit};
    """
    return execute_query(query, engine=engine)


def run_top_products_sql_query(limit: int = 20, engine=None) -> pd.DataFrame:
    """Execute Top Products query with return rate and net revenue."""
    query = f"""
    SELECT
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
    LIMIT {limit};
    """
    return execute_query(query, engine=engine)


def run_integrity_check_sql(engine=None) -> Dict[str, pd.DataFrame]:
    """Execute verification queries to audit database consistency."""
    eng = engine or get_engine()
    results = {}

    q1 = """
    SELECT
        'cleaned_transactions' AS table_name,
        COUNT(*) AS total_rows,
        COUNT(DISTINCT invoice_no) AS distinct_invoices,
        COUNT(DISTINCT customer_id) AS distinct_customers,
        MIN(invoice_date) AS min_date,
        MAX(invoice_date) AS max_date
    FROM cleaned_transactions
    UNION ALL
    SELECT
        'raw_transactions' AS table_name,
        COUNT(*) AS total_rows,
        COUNT(DISTINCT invoice_no) AS distinct_invoices,
        COUNT(DISTINCT customer_id) AS distinct_customers,
        MIN(invoice_date) AS min_date,
        MAX(invoice_date) AS max_date
    FROM raw_transactions;
    """
    try:
        results["table_counts"] = execute_query(q1, engine=eng)
    except Exception as e:
        results["table_counts"] = pd.DataFrame([{"error": str(e)}])

    q2 = """
    SELECT
        ROUND(SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END), 2) AS gross_sales,
        ROUND(SUM(CASE WHEN is_cancelled THEN ABS(line_total) ELSE 0 END), 2) AS returned_value,
        ROUND(SUM(line_total), 2) AS net_revenue,
        ROUND(
            SUM(CASE WHEN NOT is_cancelled THEN line_total ELSE 0 END) -
            SUM(CASE WHEN is_cancelled THEN ABS(line_total) ELSE 0 END) -
            SUM(line_total), 4
        ) AS arithmetic_discrepancy
    FROM cleaned_transactions;
    """
    try:
        results["revenue_reconciliation"] = execute_query(q2, engine=eng)
    except Exception as e:
        results["revenue_reconciliation"] = pd.DataFrame([{"error": str(e)}])

    q3 = """
    SELECT
        is_guest,
        COUNT(*) AS row_count,
        ROUND((COUNT(*)::NUMERIC / (SELECT COUNT(*) FROM cleaned_transactions)) * 100.0, 2) AS row_percentage,
        COUNT(DISTINCT invoice_no) AS invoice_count,
        ROUND(SUM(line_total), 2) AS net_revenue,
        ROUND((SUM(line_total) / (SELECT SUM(line_total) FROM cleaned_transactions)) * 100.0, 2) AS revenue_percentage
    FROM cleaned_transactions
    GROUP BY is_guest;
    """
    try:
        results["guest_impact"] = execute_query(q3, engine=eng)
    except Exception as e:
        results["guest_impact"] = pd.DataFrame([{"error": str(e)}])

    return results
