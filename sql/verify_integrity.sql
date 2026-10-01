-- ==============================================================================
-- Data Integrity & Audit Verification Queries
-- ==============================================================================

-- 1. Verify Overall Table Record Counts and Date Spans
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

-- 2. Verify Revenue Reconciliation: Gross - Returns = Net
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

-- 3. Verify Null Customer Impact
SELECT
    is_guest,
    COUNT(*) AS row_count,
    ROUND((COUNT(*)::NUMERIC / (SELECT COUNT(*) FROM cleaned_transactions)) * 100.0, 2) AS row_percentage,
    COUNT(DISTINCT invoice_no) AS invoice_count,
    ROUND(SUM(line_total), 2) AS net_revenue,
    ROUND((SUM(line_total) / (SELECT SUM(line_total) FROM cleaned_transactions)) * 100.0, 2) AS revenue_percentage
FROM cleaned_transactions
GROUP BY is_guest;

-- 4. Check for Any Anomalous Non-Positive Prices in Cleaned Table
SELECT
    COUNT(*) AS invalid_price_count
FROM cleaned_transactions
WHERE unit_price <= 0;
