"""
Tests for Data Cleaning and Validation pipeline.
"""

import pandas as pd
import pytest
from src.data_cleaning import DataCleaner, clean_dataset


@pytest.fixture
def sample_raw_data():
    """Fixture providing a mock raw dataset with known edge cases."""
    data = [
        # Normal transaction
        {"InvoiceNo": "536365", "StockCode": "85123A", "Description": "WHITE HANGING HEART", "Quantity": 6, "InvoiceDate": "2010-12-01 08:26:00", "UnitPrice": 2.55, "CustomerID": 17850, "Country": "United Kingdom"},
        # Exact duplicate of the first row
        {"InvoiceNo": "536365", "StockCode": "85123A", "Description": "WHITE HANGING HEART", "Quantity": 6, "InvoiceDate": "2010-12-01 08:26:00", "UnitPrice": 2.55, "CustomerID": 17850, "Country": "United Kingdom"},
        # Cancelled transaction ('C' prefix, negative quantity)
        {"InvoiceNo": "C536379", "StockCode": "D", "Description": "Discount", "Quantity": -1, "InvoiceDate": "2010-12-01 09:41:00", "UnitPrice": 27.50, "CustomerID": 14527, "Country": "United Kingdom"},
        # Product cancellation with normal stock code
        {"InvoiceNo": "C536383", "StockCode": "35004C", "Description": "SET OF 3 COLOURED  FLYING DUCKS", "Quantity": -1, "InvoiceDate": "2010-12-01 09:49:00", "UnitPrice": 4.65, "CustomerID": 15311, "Country": "United Kingdom"},
        # Zero price record (inventory adjustment / lost item)
        {"InvoiceNo": "536414", "StockCode": "22139", "Description": "damages", "Quantity": 56, "InvoiceDate": "2010-12-01 11:52:00", "UnitPrice": 0.00, "CustomerID": None, "Country": "United Kingdom"},
        # Negative price anomaly
        {"InvoiceNo": "A563185", "StockCode": "B", "Description": "Adjust bad debt", "Quantity": 1, "InvoiceDate": "2011-08-12 14:50:00", "UnitPrice": -11062.06, "CustomerID": None, "Country": "United Kingdom"},
        # Administrative stock code (POST)
        {"InvoiceNo": "536370", "StockCode": "POST", "Description": "POSTAGE", "Quantity": 3, "InvoiceDate": "2010-12-01 08:45:00", "UnitPrice": 18.00, "CustomerID": 12583, "Country": "France"},
        # Guest checkout (null CustomerID) with valid merchandise
        {"InvoiceNo": "536415", "StockCode": "22960", "Description": "JAM MAKING SET WITH JARS", "Quantity": 6, "InvoiceDate": "2010-12-01 11:57:00", "UnitPrice": 4.25, "CustomerID": None, "Country": "United Kingdom"},
    ]
    return pd.DataFrame(data)


def test_duplicate_removal(sample_raw_data):
    """Verify that exact duplicates are eliminated."""
    cleaner = DataCleaner(sample_raw_data)
    cleaned_df, steps = cleaner.run_pipeline(remove_admin_codes=False)
    # The duplicate of invoice 536365 should be removed
    assert len(cleaned_df[cleaned_df["InvoiceNo"] == "536365"]) == 1
    dup_step = next(s for s in steps if s.step_name == "2_EXACT_DUPLICATES")
    assert dup_step.records_impacted == 1


def test_invalid_price_removal(sample_raw_data):
    """Verify that UnitPrice <= 0 records are eliminated."""
    cleaner = DataCleaner(sample_raw_data)
    cleaned_df, steps = cleaner.run_pipeline(remove_admin_codes=False)
    assert (cleaned_df["UnitPrice"] <= 0).sum() == 0
    price_step = next(s for s in steps if s.step_name == "3_INVALID_PRICE")
    assert price_step.records_impacted == 2  # UnitPrice 0.00 and -11062.06


def test_administrative_codes_filtering(sample_raw_data):
    """Verify that administrative codes like POST, D, B are filtered when requested."""
    cleaner = DataCleaner(sample_raw_data)
    cleaned_df, steps = cleaner.run_pipeline(remove_admin_codes=True)
    admin_stock_codes = ["POST", "D", "B"]
    for code in admin_stock_codes:
        assert code not in cleaned_df["StockCode"].values


def test_cancellation_tagging(sample_raw_data):
    """Verify that cancellations are correctly identified and tagged."""
    cleaner = DataCleaner(sample_raw_data)
    cleaned_df, _ = cleaner.run_pipeline(remove_admin_codes=False)
    cancelled_rows = cleaned_df[cleaned_df["InvoiceNo"] == "C536383"]
    assert len(cancelled_rows) == 1
    assert bool(cancelled_rows["is_cancelled"].iloc[0]) is True
    assert bool(cancelled_rows["is_return"].iloc[0]) is True
    assert cancelled_rows["LineTotal"].iloc[0] < 0


def test_guest_checkout_preservation(sample_raw_data):
    """Verify that guest checkouts are preserved with is_guest=True."""
    cleaner = DataCleaner(sample_raw_data)
    cleaned_df, _ = cleaner.run_pipeline(remove_unidentified_customers=False)
    guest_rows = cleaned_df[cleaned_df["InvoiceNo"] == "536415"]
    assert len(guest_rows) == 1
    assert bool(guest_rows["is_guest"].iloc[0]) is True
    assert guest_rows["CustomerID_Clean"].iloc[0] == "GUEST"
