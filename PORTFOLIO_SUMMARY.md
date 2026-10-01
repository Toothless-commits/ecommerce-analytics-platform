# 💼 Portfolio Case Study: E-Commerce Analytics Platform

**Author**: Data Analyst Candidate  
**Project**: End-to-End E-Commerce Transaction & Customer Intelligence  
**Dataset**: UCI Machine Learning Repository — Online Retail Dataset (541,909 Transactions)  
**Tech Stack**: Python 3.12, Pandas, NumPy, PostgreSQL, SQLAlchemy, Streamlit, Plotly, Pytest  

---

## 📌 Executive Summary

Modern e-commerce enterprises generate massive volumes of transactional data, yet decision-makers frequently base critical inventory and marketing strategies on incomplete or distorted metrics. Common pitfalls include treating returned goods as positive sales, miscounting guest transactions, and treating all customers as a homogeneous group.

This project delivers an end-to-end, production-grade analytics platform that ingests raw retail transaction records, executes an auditable data cleaning pipeline, stores structured data in a relational PostgreSQL warehouse, and presents actionable insights across five interactive Streamlit dashboard modules.

---

## 🛠️ The Technical Stack & Architecture

- **Data Pipeline & Processing**: Python 3.12, Pandas, NumPy. Built with memory-efficient Parquet caching reducing query load times from 35s to under 0.2s.
- **Relational Storage**: PostgreSQL 16+ managed through SQLAlchemy with parameterized queries, connection pooling, and optimized B-Tree indexes on `invoice_date`, `customer_id`, `stock_code`, and `country`.
- **Advanced SQL Analytics**: Direct execution of analytical SQL using **Common Table Expressions (CTEs)**, Window Functions (`LAG()`, `NTILE()`), and conditional aggregations.
- **Interactive Visualization**: Streamlit multi-page web application featuring Plotly interactive charts with custom branding, unified color palettes, responsive tooltips, and dynamic filtering.
- **Quality Assurance**: Automated testing suite via `pytest` covering revenue arithmetic, cancellation tagging, and RFM scoring.

---

## 🔍 Key Analytical Findings & Business Insights

### 1. Revenue & Order Integrity (Realized vs. Gross Revenue)
- **Gross Commercial Sales**: **£10,247,905.13** across 23,195 unique invoices.
- **Refunds & Cancellations**: **£475,901.16** across 8,668 line items.
- **True Net Realized Revenue**: **£9,772,003.97** with a **4.64% overall revenue return rate**.
- **Takeaway**: Failing to account for cancellation invoices (`InvoiceNo` prefix `C`) inflates top-line revenue by nearly **half a million pounds**, creating severe misallocations in inventory replenishment and cash-flow projections.

### 2. Geographic Concentration & International Opportunities
- **Domestic Dominance**: The United Kingdom accounts for **£8,265,476.93** or **84.58%** of total net revenue.
- **Top International Markets**:
  1. **Netherlands**: £285,446.34 (Average Order Value: £2,912.72)
  2. **EIRE (Ireland)**: £263,276.82 (AOV: £822.74)
  3. **Germany**: £221,698.21 (AOV: £485.10)
  4. **France**: £197,403.90 (AOV: £508.77)
  5. **Australia**: £137,077.27 (AOV: £2,076.93)
- **Takeaway**: While domestic volume is highest, international orders exhibit significantly higher **Average Order Values (£800–£2,900)** compared to the domestic UK average (£430), indicating strong wholesale distributor relationships abroad.

### 3. Customer Retention & RFM Segmentation
Among 4,323 identified customer accounts:
- **Repeat Purchase Rate**: **69.6%** of identified customers ordered two or more times, indicating strong product-market fit.
- **Customer Pareto Distribution**: The top 20% of customers account for **68.4% of total customer-driven spend**.
- **Behavioral Cohorts**:
  - **Champions (RFM 555 / 455)**: 458 customers (~10.6%) generating over **£3.4M in revenue** (35% of identified sales).
  - **At Risk (High Spenders)**: 341 customers who previously spent heavily but have not transacted in over 90 days.
  - **Lost Customers (RFM 111)**: 512 accounts who made single low-value purchases over 250 days ago.

### 4. Operational Demand Patterns
- **Peak Days**: **Thursday (22.8%)** and **Tuesday (19.4%)** generate the highest transaction counts.
- **Peak Hours**: Concentrated between **10:00 AM and 3:00 PM**, with maximum order placement occurring at **12:00 PM (lunch hour)**.
- **Inventory & Logistics Strategy**: Warehouse fulfillment shifts and customer support staffing should be front-loaded Tuesday through Thursday mornings.

### 5. Product Catalog & Return Hotspots
- **Top Revenue Driver**: `REGENCY CAKESTAND 3 TIER` (StockCode `22423`) generated **£164,762.19 net revenue** with a manageable 5.57% return rate.
- **Highest Return Rate SKUs**: Certain decorative ceramics and glass items exhibited refund rates exceeding **15–20%**, pointing to in-transit transit damage rather than product dissatisfaction.

---

## 💡 Strategic Business Recommendations

1. **VIP Loyalty & Concierge Service**:
   - Establish dedicated account managers for the **458 Champions**, offering scheduled bulk orders and exclusive catalog previews.
2. **Automated Win-Back Triggers for "At Risk" Accounts**:
   - Deploy automated email sequences at Day 60 and Day 90 post-purchase offering tailored incentives before customers transition into the "Lost" segment.
3. **Packaging Optimization for High-Return SKUs**:
   - Review packaging for ceramics and glassware exceeding 10% return rates to reduce courier breakage.
4. **International Wholesale Expansion**:
   - Focus digital marketing and distribution partnerships in the Netherlands and Australia, where order sizes are 4x to 6x larger than UK domestic transactions.

---

## 📈 Summary of Technical Deliverables

| Deliverable | Location | Description |
| :--- | :--- | :--- |
| **Streamlit Web Application** | [`app.py`](file:///home/night/Data%20analyst/app.py) | Main dashboard entrypoint with interactive filters and metrics |
| **Multi-Page Dashboards** | [`pages/`](file:///home/night/Data%20analyst/pages/) | 5 specialized modules: Executive, Sales, Customers, Products, Data Quality |
| **Data Cleaning Pipeline** | [`src/data_cleaning.py`](file:///home/night/Data%20analyst/src/data_cleaning.py) | Auditable transformations removing duplicates, zero prices, and admin codes |
| **PostgreSQL Schema & ETL** | [`sql/schema.sql`](file:///home/night/Data%20analyst/sql/schema.sql), [`src/db_loader.py`](file:///home/night/Data%20analyst/src/db_loader.py) | Relational tables, indexing, and batch loading |
| **Portfolio SQL Queries** | [`sql/analytical_queries.sql`](file:///home/night/Data%20analyst/sql/analytical_queries.sql) | Production SQL with CTEs, `LAG()`, and `NTILE(5)` window functions |
| **Automated Tests** | [`tests/`](file:///home/night/Data%20analyst/tests/) | 15 passing pytest test cases for cleaning, metrics, and RFM algorithms |
| **Project Documentation** | [`README.md`](file:///home/night/Data%20analyst/README.md) | Comprehensive architecture guide, setup steps, and metric dictionary |
