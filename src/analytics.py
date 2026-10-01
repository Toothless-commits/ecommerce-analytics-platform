"""
Core Analytics Engine.
Calculates e-commerce KPIs, revenue metrics, time series trends,
cohort retention matrices, and RFM customer segmentation.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_executive_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate executive-level commercial KPIs with strict accounting rules.
    - Gross Sales: Positive transaction lines (Quantity > 0 and UnitPrice > 0)
    - Returns / Cancellations: Negative transaction lines (Quantity < 0 or is_cancelled)
    - Net Revenue: Gross Sales - Refund Value
    - Purchase Orders: Unique invoice count for positive sales
    - Identified Customers: Unique non-null Customer IDs
    - Average Order Value (AOV): Gross Sales / Purchase Orders
    """
    if df.empty:
        return {
            "gross_revenue": 0.0,
            "returns_revenue": 0.0,
            "net_revenue": 0.0,
            "return_rate_pct": 0.0,
            "purchase_orders": 0,
            "cancellation_orders": 0,
            "total_invoices": 0,
            "unique_customers": 0,
            "guest_invoices": 0,
            "guest_revenue_pct": 0.0,
            "gross_aov": 0.0,
            "net_aov": 0.0,
            "units_sold": 0,
            "units_returned": 0,
            "net_units": 0,
            "avg_items_per_order": 0.0,
        }

    sales_mask = ~df["is_cancelled"] & (df["Quantity"] > 0)
    returns_mask = df["is_cancelled"] | (df["Quantity"] < 0)

    gross_revenue = float(df.loc[sales_mask, "LineTotal"].sum())
    returns_revenue = float(df.loc[returns_mask, "LineTotal"].abs().sum())
    net_revenue = gross_revenue - returns_revenue

    return_rate_pct = (returns_revenue / gross_revenue * 100.0) if gross_revenue > 0 else 0.0

    purchase_orders = int(df.loc[sales_mask, "InvoiceNo"].nunique())
    cancellation_orders = int(df.loc[returns_mask, "InvoiceNo"].nunique())
    total_invoices = int(df["InvoiceNo"].nunique())

    # Customer counts
    identified_custs = df[~df["is_guest"] & df["CustomerID"].notna()]
    unique_customers = int(identified_custs["CustomerID"].nunique())

    guest_orders = int(df[df["is_guest"]]["InvoiceNo"].nunique())
    guest_revenue = float(df.loc[df["is_guest"] & sales_mask, "LineTotal"].sum())
    guest_revenue_pct = (guest_revenue / gross_revenue * 100.0) if gross_revenue > 0 else 0.0

    gross_aov = (gross_revenue / purchase_orders) if purchase_orders > 0 else 0.0
    net_aov = (net_revenue / purchase_orders) if purchase_orders > 0 else 0.0

    units_sold = int(df.loc[sales_mask, "Quantity"].sum())
    units_returned = int(df.loc[returns_mask, "Quantity"].abs().sum())
    net_units = units_sold - units_returned

    avg_items_per_order = (units_sold / purchase_orders) if purchase_orders > 0 else 0.0

    return {
        "gross_revenue": round(gross_revenue, 2),
        "returns_revenue": round(returns_revenue, 2),
        "net_revenue": round(net_revenue, 2),
        "return_rate_pct": round(return_rate_pct, 2),
        "purchase_orders": purchase_orders,
        "cancellation_orders": cancellation_orders,
        "total_invoices": total_invoices,
        "unique_customers": unique_customers,
        "guest_invoices": guest_orders,
        "guest_revenue_pct": round(guest_revenue_pct, 2),
        "gross_aov": round(gross_aov, 2),
        "net_aov": round(net_aov, 2),
        "units_sold": units_sold,
        "units_returned": units_returned,
        "net_units": net_units,
        "avg_items_per_order": round(avg_items_per_order, 1),
    }


def get_revenue_trend(df: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """
    Generate time series aggregations with period-over-period growth rates.
    freq: 'D' (daily), 'W' (weekly), 'M' (monthly).
    """
    if df.empty:
        return pd.DataFrame()

    df_copy = df.copy()
    if freq == "D":
        df_copy["period"] = pd.to_datetime(df_copy["InvoiceDate"]).dt.to_period("D").dt.to_timestamp()
    elif freq == "W":
        df_copy["period"] = pd.to_datetime(df_copy["InvoiceDate"]).dt.to_period("W").dt.to_timestamp()
    else:
        df_copy["period"] = pd.to_datetime(df_copy["InvoiceDate"]).dt.to_period("M").dt.to_timestamp()

    # Aggregate
    agg = df_copy.groupby("period").apply(
        lambda g: pd.Series(
            {
                "gross_revenue": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "LineTotal"].sum(),
                "refund_amount": g.loc[g["is_cancelled"] | (g["Quantity"] < 0), "LineTotal"].abs().sum(),
                "net_revenue": g["LineTotal"].sum(),
                "orders": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "InvoiceNo"].nunique(),
                "customers": g.loc[~g["is_guest"], "CustomerID"].nunique(),
                "units_sold": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "Quantity"].sum(),
            }
        ),
        include_groups=False,
    ).reset_index()

    agg = agg.sort_values("period").reset_index(drop=True)
    agg["aov"] = (agg["gross_revenue"] / agg["orders"].replace(0, np.nan)).fillna(0.0)
    agg["mom_net_growth_pct"] = agg["net_revenue"].pct_change() * 100.0
    agg["mom_order_growth_pct"] = agg["orders"].pct_change() * 100.0
    agg["rolling_7p_net_revenue"] = agg["net_revenue"].rolling(window=7, min_periods=1).mean()

    return agg


def get_top_products(
    df: pd.DataFrame, top_n: int = 15, sort_by: str = "net_revenue"
) -> pd.DataFrame:
    """
    Aggregate merchandise product performance including gross, refunds, net, and return rate.
    """
    if df.empty:
        return pd.DataFrame()

    # Group by StockCode
    grouped = df.groupby("StockCode").apply(
        lambda g: pd.Series(
            {
                "description": g["Description"].mode().iloc[0] if not g["Description"].empty else "Unknown",
                "units_sold": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "Quantity"].sum(),
                "units_returned": g.loc[g["is_cancelled"] | (g["Quantity"] < 0), "Quantity"].abs().sum(),
                "gross_sales": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "LineTotal"].sum(),
                "refund_amount": g.loc[g["is_cancelled"] | (g["Quantity"] < 0), "LineTotal"].abs().sum(),
                "net_revenue": g["LineTotal"].sum(),
                "order_count": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "InvoiceNo"].nunique(),
            }
        ),
        include_groups=False,
    ).reset_index()

    # Return rate
    grouped["return_rate_qty_pct"] = (
        grouped["units_returned"] / (grouped["units_sold"] + grouped["units_returned"]).replace(0, np.nan) * 100.0
    ).fillna(0.0)

    grouped["return_rate_rev_pct"] = (
        grouped["refund_amount"] / grouped["gross_sales"].replace(0, np.nan) * 100.0
    ).fillna(0.0)

    sort_col = sort_by if sort_by in grouped.columns else "net_revenue"
    return grouped.sort_values(sort_col, ascending=False).head(top_n).reset_index(drop=True)


def get_country_performance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Geographic breakdown of orders, customers, and revenue.
    """
    if df.empty:
        return pd.DataFrame()

    agg = df.groupby("Country").apply(
        lambda g: pd.Series(
            {
                "total_orders": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "InvoiceNo"].nunique(),
                "unique_customers": g.loc[~g["is_guest"], "CustomerID"].nunique(),
                "gross_revenue": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "LineTotal"].sum(),
                "refund_amount": g.loc[g["is_cancelled"] | (g["Quantity"] < 0), "LineTotal"].abs().sum(),
                "net_revenue": g["LineTotal"].sum(),
            }
        ),
        include_groups=False,
    ).reset_index()

    total_net = agg["net_revenue"].sum()
    agg["revenue_share_pct"] = (agg["net_revenue"] / total_net * 100.0) if total_net > 0 else 0.0
    agg["aov"] = (agg["gross_revenue"] / agg["total_orders"].replace(0, np.nan)).fillna(0.0)

    return agg.sort_values("net_revenue", ascending=False).reset_index(drop=True)


def calculate_rfm(
    df: pd.DataFrame, reference_date: Optional[pd.Timestamp] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Perform RFM (Recency, Frequency, Monetary) segmentation.
    1. Filter out guest checkouts (requires identified CustomerID).
    2. Recency: Days since customer's last purchase relative to reference date.
    3. Frequency: Count of distinct purchase invoices.
    4. Monetary: Total net revenue from customer.
    5. Scoring: 1-5 quintiles for R, F, and M.
    6. Segment Mapping: Champions, Loyal Customers, Potential Loyalists, At Risk, etc.
    """
    # Filter to identified customers only
    identified = df[~df["is_guest"] & df["CustomerID"].notna()].copy()
    if identified.empty:
        return pd.DataFrame(), {}

    ref_date = reference_date or (pd.to_datetime(identified["InvoiceDate"]).max() + pd.Timedelta(days=1))

    # Customer level aggregation
    rfm_table = identified.groupby("CustomerID").apply(
        lambda g: pd.Series(
            {
                "FirstPurchaseDate": g.loc[~g["is_cancelled"], "InvoiceDate"].min(),
                "LastPurchaseDate": g.loc[~g["is_cancelled"], "InvoiceDate"].max(),
                "Frequency": g.loc[~g["is_cancelled"] & (g["Quantity"] > 0), "InvoiceNo"].nunique(),
                "Monetary": g["LineTotal"].sum(),
                "Units": g.loc[~g["is_cancelled"], "Quantity"].sum(),
                "ReturnsCount": g.loc[g["is_cancelled"], "InvoiceNo"].nunique(),
                "Country": g["Country"].mode().iloc[0] if not g["Country"].empty else "Unknown",
            }
        ),
        include_groups=False,
    ).reset_index()

    # Filter out customers with 0 purchases or non-positive spend
    rfm_table = rfm_table[(rfm_table["Frequency"] > 0) & (rfm_table["Monetary"] > 0)].copy()
    if rfm_table.empty:
        return pd.DataFrame(), {}

    # Recency days
    rfm_table["Recency"] = (ref_date - pd.to_datetime(rfm_table["LastPurchaseDate"])).dt.days

    # Scoring into 1-5 quintiles
    # R: Lower recency -> Higher score (5 is best)
    rfm_table["R_Score"] = pd.qcut(
        rfm_table["Recency"].rank(method="first", ascending=False),
        q=5,
        labels=[1, 2, 3, 4, 5],
    ).astype(int)

    # F: Higher frequency -> Higher score (5 is best)
    rfm_table["F_Score"] = pd.qcut(
        rfm_table["Frequency"].rank(method="first", ascending=True),
        q=5,
        labels=[1, 2, 3, 4, 5],
    ).astype(int)

    # M: Higher monetary -> Higher score (5 is best)
    rfm_table["M_Score"] = pd.qcut(
        rfm_table["Monetary"].rank(method="first", ascending=True),
        q=5,
        labels=[1, 2, 3, 4, 5],
    ).astype(int)

    rfm_table["RFM_Score"] = (
        rfm_table["R_Score"].astype(str)
        + rfm_table["F_Score"].astype(str)
        + rfm_table["M_Score"].astype(str)
    )

    # Segment mapping based on R, F, M combinations
    def assign_segment(row) -> str:
        r, f, m = row["R_Score"], row["F_Score"], row["M_Score"]
        rf_avg = (r + f) / 2.0

        if r >= 4 and f >= 4 and m >= 4:
            return "Champions"
        if r >= 3 and f >= 3 and m >= 3:
            return "Loyal Customers"
        if r >= 4 and f in [1, 2]:
            return "New / Potential Loyalists"
        if r in [2, 3] and f in [2, 3]:
            return "Promising / Regular"
        if r <= 2 and f >= 3 and m >= 3:
            return "At Risk (High Spenders)"
        if r == 1 and f >= 4:
            return "Can't Lose Them"
        if r <= 2 and f <= 2 and m >= 3:
            return "About to Sleep"
        if r == 1 and f == 1:
            return "Lost Customers"
        return "Hibernating"

    rfm_table["Segment"] = rfm_table.apply(assign_segment, axis=1)

    # Summary statistics
    segment_summary = rfm_table.groupby("Segment").agg(
        customer_count=("CustomerID", "count"),
        avg_recency=("Recency", "mean"),
        avg_frequency=("Frequency", "mean"),
        avg_monetary=("Monetary", "mean"),
        total_monetary=("Monetary", "sum"),
    ).reset_index()

    total_spend = segment_summary["total_monetary"].sum()
    segment_summary["monetary_share_pct"] = (segment_summary["total_monetary"] / total_spend * 100.0).round(2)
    segment_summary["customer_share_pct"] = (
        segment_summary["customer_count"] / len(rfm_table) * 100.0
    ).round(2)

    stats = {
        "total_rfm_customers": len(rfm_table),
        "avg_recency_days": round(rfm_table["Recency"].mean(), 1),
        "avg_frequency": round(rfm_table["Frequency"].mean(), 1),
        "avg_monetary": round(rfm_table["Monetary"].mean(), 2),
        "median_monetary": round(rfm_table["Monetary"].median(), 2),
        "segment_summary": segment_summary.to_dict(orient="records"),
    }

    return rfm_table, stats


def calculate_cohort_retention(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate customer acquisition cohort retention matrix.
    Returns:
        (retention_matrix_pct, retention_matrix_counts)
    """
    # Require identified customer IDs and non-cancelled purchases
    clean = df[~df["is_guest"] & df["CustomerID"].notna() & ~df["is_cancelled"]].copy()
    if clean.empty:
        return pd.DataFrame(), pd.DataFrame()

    clean["InvoiceMonth"] = pd.to_datetime(clean["InvoiceDate"]).dt.to_period("M")

    # Cohort Month: Month of customer's first purchase
    cohort_first = clean.groupby("CustomerID")["InvoiceMonth"].min().reset_index()
    cohort_first = cohort_first.rename(columns={"InvoiceMonth": "CohortMonth"})

    merged = clean.merge(cohort_first, on="CustomerID")

    # Period index: offset in months from first purchase
    def get_month_offset(row):
        return (row["InvoiceMonth"].year - row["CohortMonth"].year) * 12 + (
            row["InvoiceMonth"].month - row["CohortMonth"].month
        )

    merged["CohortIndex"] = merged.apply(get_month_offset, axis=1)

    # Group by CohortMonth and CohortIndex
    cohort_data = merged.groupby(["CohortMonth", "CohortIndex"])["CustomerID"].nunique().reset_index()
    cohort_counts = cohort_data.pivot(index="CohortMonth", columns="CohortIndex", values="CustomerID")

    # Cohort size (Month 0)
    cohort_sizes = cohort_counts.iloc[:, 0]
    cohort_pct = cohort_counts.divide(cohort_sizes, axis=0) * 100.0

    cohort_counts.index = cohort_counts.index.astype(str)
    cohort_pct.index = cohort_pct.index.astype(str)

    return cohort_pct, cohort_counts


def get_sales_time_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create DayOfWeek vs Hour cross-tab matrix of order volume.
    """
    if df.empty:
        return pd.DataFrame()

    sales = df[~df["is_cancelled"] & (df["Quantity"] > 0)].copy()
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    matrix = sales.pivot_table(
        index="DayOfWeek",
        columns="Hour",
        values="InvoiceNo",
        aggfunc="nunique",
        fill_value=0,
    )

    # Reindex to standard calendar days
    existing_days = [d for d in days_order if d in matrix.index]
    return matrix.reindex(existing_days)
