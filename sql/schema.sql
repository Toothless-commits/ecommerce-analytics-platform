-- ==============================================================================
-- Schema Definition for E-Commerce Analytics Platform (PostgreSQL)
-- ==============================================================================

-- 1. Raw Transactions (Mirror of Ingested Dataset)
CREATE TABLE IF NOT EXISTS raw_transactions (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(64),
    stock_code VARCHAR(64),
    description TEXT,
    quantity INT,
    invoice_date TIMESTAMP,
    unit_price NUMERIC(12, 4),
    customer_id VARCHAR(64),
    country VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for raw querying
CREATE INDEX IF NOT EXISTS idx_raw_invoice_date ON raw_transactions(invoice_date);
CREATE INDEX IF NOT EXISTS idx_raw_customer_id ON raw_transactions(customer_id);

-- 2. Cleaned & Enriched Transactions (Primary Analytics Fact Table)
CREATE TABLE IF NOT EXISTS cleaned_transactions (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(64) NOT NULL,
    stock_code VARCHAR(64) NOT NULL,
    description TEXT,
    quantity INT NOT NULL,
    invoice_date TIMESTAMP NOT NULL,
    unit_price NUMERIC(12, 4) NOT NULL,
    customer_id VARCHAR(64),
    country VARCHAR(128) NOT NULL,
    is_cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    is_return BOOLEAN NOT NULL DEFAULT FALSE,
    is_guest BOOLEAN NOT NULL DEFAULT FALSE,
    line_total NUMERIC(14, 4) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    year_month VARCHAR(7) NOT NULL,
    day_of_week VARCHAR(16) NOT NULL,
    hour INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Optimized Analytical Indexes
CREATE INDEX IF NOT EXISTS idx_clean_invoice_date ON cleaned_transactions(invoice_date);
CREATE INDEX IF NOT EXISTS idx_clean_customer_id ON cleaned_transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_clean_stock_code ON cleaned_transactions(stock_code);
CREATE INDEX IF NOT EXISTS idx_clean_country ON cleaned_transactions(country);
CREATE INDEX IF NOT EXISTS idx_clean_year_month ON cleaned_transactions(year_month);
CREATE INDEX IF NOT EXISTS idx_clean_is_cancelled ON cleaned_transactions(is_cancelled);
CREATE INDEX IF NOT EXISTS idx_clean_is_guest ON cleaned_transactions(is_guest);

-- 3. Customer RFM Dimension Table
CREATE TABLE IF NOT EXISTS customer_rfm (
    customer_id VARCHAR(64) PRIMARY KEY,
    recency_days INT NOT NULL,
    frequency_orders INT NOT NULL,
    monetary_spend NUMERIC(14, 4) NOT NULL,
    r_score INT NOT NULL,
    f_score INT NOT NULL,
    m_score INT NOT NULL,
    rfm_score VARCHAR(8) NOT NULL,
    customer_segment VARCHAR(64) NOT NULL,
    first_purchase_date TIMESTAMP,
    last_purchase_date TIMESTAMP,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rfm_segment ON customer_rfm(customer_segment);
CREATE INDEX IF NOT EXISTS idx_rfm_score ON customer_rfm(rfm_score);

-- 4. Cleaning Audit Trail
CREATE TABLE IF NOT EXISTS cleaning_audit_log (
    id SERIAL PRIMARY KEY,
    step_name VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    records_before INT NOT NULL,
    records_after INT NOT NULL,
    records_impacted INT NOT NULL,
    pct_impacted NUMERIC(6, 3) NOT NULL,
    notes TEXT,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
