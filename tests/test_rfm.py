"""
Tests for RFM Segmentation and Scoring Engine.
"""

import pandas as pd
import pytest
from src.analytics import calculate_rfm


@pytest.fixture
def rfm_test_data():
    """Generate transactions across multiple customers spanning different recency/frequency/spend."""
    records = []
    # Customer 1: Recent, Frequent, High Spender (Candidate Champion)
    for i in range(10):
        records.append({
            "InvoiceNo": f"INV_1_{i}",
            "StockCode": "SKU_A",
            "Description": "Item A",
            "Quantity": 10,
            "UnitPrice": 100.0,
            "LineTotal": 1000.0,
            "CustomerID": "CUST_CHAMPION",
            "Country": "United Kingdom",
            "is_cancelled": False,
            "is_return": False,
            "is_guest": False,
            "InvoiceDate": pd.to_datetime("2021-12-01 10:00:00") - pd.Timedelta(days=i),
        })

    # Customer 2: Old, Single Purchase, Low Spend (Candidate Lost)
    records.append({
        "InvoiceNo": "INV_2_0",
        "StockCode": "SKU_B",
        "Description": "Item B",
        "Quantity": 1,
        "UnitPrice": 10.0,
        "LineTotal": 10.0,
        "CustomerID": "CUST_LOST",
        "Country": "United Kingdom",
        "is_cancelled": False,
        "is_return": False,
        "is_guest": False,
        "InvoiceDate": pd.to_datetime("2021-01-01 10:00:00"),
    })

    # Add 8 more diverse customers to allow 5 quintiles
    for cust_idx in range(3, 11):
        for order_idx in range(cust_idx % 4 + 1):
            records.append({
                "InvoiceNo": f"INV_{cust_idx}_{order_idx}",
                "StockCode": "SKU_C",
                "Description": "Item C",
                "Quantity": 2 * cust_idx,
                "UnitPrice": 15.0,
                "LineTotal": 30.0 * cust_idx,
                "CustomerID": f"CUST_{cust_idx}",
                "Country": "France",
                "is_cancelled": False,
                "is_return": False,
                "is_guest": False,
                "InvoiceDate": pd.to_datetime("2021-12-01 10:00:00") - pd.Timedelta(days=cust_idx * 20),
            })

    # Guest checkout (must be ignored by RFM)
    records.append({
        "InvoiceNo": "INV_GUEST",
        "StockCode": "SKU_G",
        "Description": "Guest Item",
        "Quantity": 50,
        "UnitPrice": 100.0,
        "LineTotal": 5000.0,
        "CustomerID": None,
        "Country": "United Kingdom",
        "is_cancelled": False,
        "is_return": False,
        "is_guest": True,
        "InvoiceDate": pd.to_datetime("2021-12-01 10:00:00"),
    })

    return pd.DataFrame(records)


def test_rfm_score_boundaries(rfm_test_data):
    """Verify that R, F, and M scores are integers between 1 and 5."""
    ref_date = pd.to_datetime("2021-12-05")
    rfm_df, stats = calculate_rfm(rfm_test_data, reference_date=ref_date)

    assert not rfm_df.empty
    assert rfm_df["R_Score"].between(1, 5).all()
    assert rfm_df["F_Score"].between(1, 5).all()
    assert rfm_df["M_Score"].between(1, 5).all()
    assert rfm_df["RFM_Score"].str.len().eq(3).all()


def test_guest_exclusion_from_rfm(rfm_test_data):
    """Ensure guest checkouts (null CustomerID) are not present in RFM output."""
    rfm_df, _ = calculate_rfm(rfm_test_data)
    assert None not in rfm_df["CustomerID"].values
    assert "None" not in rfm_df["CustomerID"].values
    assert "GUEST" not in rfm_df["CustomerID"].values


def test_champion_and_lost_segment_assignment(rfm_test_data):
    """Verify high-frequency recent spender is Champion and old low-frequency is Lost/Hibernating."""
    ref_date = pd.to_datetime("2021-12-05")
    rfm_df, _ = calculate_rfm(rfm_test_data, reference_date=ref_date)

    champ_row = rfm_df[rfm_df["CustomerID"] == "CUST_CHAMPION"].iloc[0]
    assert champ_row["Segment"] in ["Champions", "Loyal Customers"]
    assert champ_row["R_Score"] >= 4
    assert champ_row["M_Score"] == 5

    lost_row = rfm_df[rfm_df["CustomerID"] == "CUST_LOST"].iloc[0]
    assert lost_row["Segment"] in ["Lost Customers", "Hibernating", "About to Sleep"]
    assert lost_row["R_Score"] == 1
    assert lost_row["F_Score"] in [1, 2]
