"""
Tests for Core Metrics, Revenue Accounting, and Aggregations.
"""

import pandas as pd
import pytest
from src.analytics import (
    calculate_executive_kpis,
    get_country_performance,
    get_revenue_trend,
    get_top_products,
)


@pytest.fixture
def sample_cleaned_data():
    """Fixture providing clean transaction records for metric tests."""
    data = [
        # Customer A: 2 orders (Order 1: 2 items, Order 2: 1 item)
        {"InvoiceNo": "1001", "StockCode": "P1", "Description": "Product 1", "Quantity": 2, "UnitPrice": 10.0, "LineTotal": 20.0, "CustomerID": "A", "Country": "United Kingdom", "is_cancelled": False, "is_return": False, "is_guest": False, "InvoiceDate": pd.to_datetime("2021-01-10 10:00:00")},
        {"InvoiceNo": "1001", "StockCode": "P2", "Description": "Product 2", "Quantity": 1, "UnitPrice": 30.0, "LineTotal": 30.0, "CustomerID": "A", "Country": "United Kingdom", "is_cancelled": False, "is_return": False, "is_guest": False, "InvoiceDate": pd.to_datetime("2021-01-10 10:00:00")},
        {"InvoiceNo": "1002", "StockCode": "P1", "Description": "Product 1", "Quantity": 3, "UnitPrice": 10.0, "LineTotal": 30.0, "CustomerID": "A", "Country": "United Kingdom", "is_cancelled": False, "is_return": False, "is_guest": False, "InvoiceDate": pd.to_datetime("2021-02-15 11:00:00")},
        # Customer B: 1 order and 1 return
        {"InvoiceNo": "1003", "StockCode": "P3", "Description": "Product 3", "Quantity": 5, "UnitPrice": 20.0, "LineTotal": 100.0, "CustomerID": "B", "Country": "Germany", "is_cancelled": False, "is_return": False, "is_guest": False, "InvoiceDate": pd.to_datetime("2021-02-16 12:00:00")},
        {"InvoiceNo": "C1004", "StockCode": "P3", "Description": "Product 3", "Quantity": -1, "UnitPrice": 20.0, "LineTotal": -20.0, "CustomerID": "B", "Country": "Germany", "is_cancelled": True, "is_return": True, "is_guest": False, "InvoiceDate": pd.to_datetime("2021-02-18 14:00:00")},
        # Guest Checkout: 1 order
        {"InvoiceNo": "1005", "StockCode": "P2", "Description": "Product 2", "Quantity": 2, "UnitPrice": 30.0, "LineTotal": 60.0, "CustomerID": None, "Country": "France", "is_cancelled": False, "is_return": False, "is_guest": True, "InvoiceDate": pd.to_datetime("2021-03-01 09:00:00")},
    ]
    return pd.DataFrame(data)


def test_revenue_arithmetic(sample_cleaned_data):
    """Test Gross Sales, Returns, and Net Revenue arithmetic."""
    kpis = calculate_executive_kpis(sample_cleaned_data)

    # Gross: 20 + 30 + 30 + 100 + 60 = 240
    assert kpis["gross_revenue"] == 240.0
    # Returns: |-20| = 20
    assert kpis["returns_revenue"] == 20.0
    # Net: 240 - 20 = 220
    assert kpis["net_revenue"] == 220.0
    # Discrepancy check: Gross - Returns - Net == 0
    assert abs((kpis["gross_revenue"] - kpis["returns_revenue"]) - kpis["net_revenue"]) < 1e-6


def test_order_counts_and_aov(sample_cleaned_data):
    """Test purchase order distinct counting and AOV derivation."""
    kpis = calculate_executive_kpis(sample_cleaned_data)

    # Invoices 1001, 1002, 1003, 1005 (total 4 purchase orders)
    assert kpis["purchase_orders"] == 4
    # Cancellation invoices: C1004 (total 1 cancellation)
    assert kpis["cancellation_orders"] == 1
    # Gross AOV = 240 / 4 = 60.0
    assert kpis["gross_aov"] == 60.0
    # Net AOV = 220 / 4 = 55.0
    assert kpis["net_aov"] == 55.0


def test_customer_counts(sample_cleaned_data):
    """Verify distinct identified customers count and guest classification."""
    kpis = calculate_executive_kpis(sample_cleaned_data)

    # Identified: Customer A and B (2 customers)
    assert kpis["unique_customers"] == 2
    # Guest invoices: 1005 (1 invoice)
    assert kpis["guest_invoices"] == 1
    # Guest revenue share: 60 / 240 = 25.0%
    assert kpis["guest_revenue_pct"] == 25.0


def test_top_products_metrics(sample_cleaned_data):
    """Test SKU aggregation with return rates."""
    top_p = get_top_products(sample_cleaned_data, top_n=5)
    # Check Product 3 has 5 sold and 1 returned
    p3 = top_p[top_p["StockCode"] == "P3"].iloc[0]
    assert p3["units_sold"] == 5
    assert p3["units_returned"] == 1
    assert p3["gross_sales"] == 100.0
    assert p3["refund_amount"] == 20.0
    assert p3["net_revenue"] == 80.0
    # Revenue return rate: 20 / 100 = 20%
    assert round(p3["return_rate_rev_pct"], 2) == 20.0


def test_empty_dataframe_kpis():
    """Verify that calculate_executive_kpis handles empty dataframes safely."""
    empty_df = pd.DataFrame(columns=["InvoiceNo", "StockCode", "Quantity", "UnitPrice", "LineTotal", "CustomerID", "Country", "is_cancelled", "is_return", "is_guest"])
    kpis = calculate_executive_kpis(empty_df)
    assert kpis["gross_revenue"] == 0.0
    assert kpis["net_revenue"] == 0.0
    assert kpis["purchase_orders"] == 0
    assert kpis["unique_customers"] == 0


def test_sales_timing_heatmap(sample_cleaned_data):
    """Verify sales time heatmap returns expected matrix structure."""
    from src.analytics import get_sales_time_heatmap
    sample_with_time = sample_cleaned_data.copy()
    sample_with_time["DayOfWeek"] = sample_with_time["InvoiceDate"].dt.day_name()
    sample_with_time["Hour"] = sample_with_time["InvoiceDate"].dt.hour
    matrix = get_sales_time_heatmap(sample_with_time)
    assert not matrix.empty
    assert 10 in matrix.columns or 11 in matrix.columns


def test_cohort_retention(sample_cleaned_data):
    """Verify cohort retention calculates percentages between 0 and 100."""
    from src.analytics import calculate_cohort_retention
    pct_matrix, counts_matrix = calculate_cohort_retention(sample_cleaned_data)
    assert not pct_matrix.empty
    # Month 0 retention should always be 100%
    assert (pct_matrix[0] == 100.0).all()
