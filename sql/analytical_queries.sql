-- ==============================================================================
-- Portfolio-Grade Analytical SQL Queries
-- Demonstrating CTEs, Window Functions (LAG, NTILE, SUM OVER), Joins, and Aggregations
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Query 1: Month-over-Month (MoM) Revenue Growth and Order Trajectory
-- Demonstrates: CTE, Aggregation, Window Function (LAG), Mathematical Derivation
-- ------------------------------------------------------------------------------
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


-- ------------------------------------------------------------------------------
-- Query 2: Direct SQL RFM Quintile Calculation
-- Demonstrates: CTEs, Window Function (NTILE), Quantile Binning, Recency logic
-- ------------------------------------------------------------------------------
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
        -- Higher recency_days means longer time ago -> lower score (5 is most recent)
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        -- Higher frequency -> higher score
        NTILE(5) OVER (ORDER BY frequency_orders ASC) AS f_score,
        -- Higher spend -> higher score
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
LIMIT 50;


-- ------------------------------------------------------------------------------
-- Query 3: Top 20 Merchandise Products with Returns & Net Margins
-- Demonstrates: Conditional Aggregation, Margin percentages, Sorting
-- ------------------------------------------------------------------------------
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
LIMIT 20;


-- ------------------------------------------------------------------------------
-- Query 4: Customer Acquisition Cohort Analysis (Monthly Retention)
-- Demonstrates: Multiple CTEs, Self-Join / Date Truncation, Retention Index
-- ------------------------------------------------------------------------------
WITH customer_first_cohort AS (
    SELECT
        customer_id,
        TO_CHAR(MIN(invoice_date), 'YYYY-MM') AS cohort_month
    FROM cleaned_transactions
    WHERE NOT is_guest AND customer_id IS NOT NULL AND NOT is_cancelled
    GROUP BY customer_id
),
customer_monthly_activities AS (
    SELECT DISTINCT
        t.customer_id,
        c.cohort_month,
        TO_CHAR(t.invoice_date, 'YYYY-MM') AS activity_month,
        (
            (DATE_PART('year', t.invoice_date) - SUBSTRING(c.cohort_month, 1, 4)::INT) * 12 +
            (DATE_PART('month', t.invoice_date) - SUBSTRING(c.cohort_month, 6, 2)::INT)
        )::INT AS period_month_offset
    FROM cleaned_transactions t
    JOIN customer_first_cohort c ON t.customer_id = c.customer_id
    WHERE NOT t.is_cancelled
),
cohort_sizes AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS cohort_size
    FROM customer_first_cohort
    GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    s.cohort_size,
    a.period_month_offset,
    COUNT(DISTINCT a.customer_id) AS active_customers,
    ROUND((COUNT(DISTINCT a.customer_id)::NUMERIC / s.cohort_size) * 100.0, 1) AS retention_rate_pct
FROM customer_monthly_activities a
JOIN cohort_sizes s ON a.cohort_month = s.cohort_month
GROUP BY a.cohort_month, s.cohort_size, a.period_month_offset
ORDER BY a.cohort_month, a.period_month_offset;
