"""
ETL Database Loader module.
Bulk loads raw and cleaned transactions, RFM segmentation,
and audit logs into PostgreSQL tables using SQLAlchemy with batching.
"""

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.db import check_db_connection, get_engine, init_db

logger = logging.getLogger(__name__)


def load_raw_to_db(
    raw_df: pd.DataFrame,
    engine: Optional[Engine] = None,
    chunksize: int = 10000,
    truncate: bool = True,
) -> int:
    """Load raw transaction records into raw_transactions table."""
    eng = engine or get_engine()

    # Normalize column names for SQL
    df_sql = pd.DataFrame(
        {
            "invoice_no": raw_df["InvoiceNo"].astype(str),
            "stock_code": raw_df["StockCode"].astype(str),
            "description": raw_df["Description"].fillna("").astype(str),
            "quantity": pd.to_numeric(raw_df["Quantity"], errors="coerce").fillna(0).astype(int),
            "invoice_date": pd.to_datetime(raw_df["InvoiceDate"], errors="coerce"),
            "unit_price": pd.to_numeric(raw_df["UnitPrice"], errors="coerce").fillna(0.0).astype(float),
            "customer_id": raw_df["CustomerID"].apply(
                lambda x: str(int(x)) if pd.notna(x) and str(x).replace(".", "").isdigit() else None
            ),
            "country": raw_df["Country"].fillna("Unspecified").astype(str),
        }
    )

    with eng.begin() as conn:
        if truncate:
            conn.execute(text("TRUNCATE TABLE raw_transactions RESTART IDENTITY;"))

    df_sql.to_sql(
        "raw_transactions",
        eng,
        if_exists="append",
        index=False,
        chunksize=chunksize,
        method="multi",
    )
    logger.info(f"Loaded {len(df_sql):,} records into raw_transactions")
    return len(df_sql)


def load_cleaned_to_db(
    cleaned_df: pd.DataFrame,
    engine: Optional[Engine] = None,
    chunksize: int = 10000,
    truncate: bool = True,
) -> int:
    """Load cleaned transaction records into cleaned_transactions table."""
    eng = engine or get_engine()

    df_sql = pd.DataFrame(
        {
            "invoice_no": cleaned_df["InvoiceNo"].astype(str),
            "stock_code": cleaned_df["StockCode"].astype(str),
            "description": cleaned_df["Description"].fillna("").astype(str),
            "quantity": cleaned_df["Quantity"].astype(int),
            "invoice_date": pd.to_datetime(cleaned_df["InvoiceDate"]),
            "unit_price": cleaned_df["UnitPrice"].astype(float),
            "customer_id": cleaned_df["CustomerID"].apply(
                lambda x: str(int(x)) if pd.notna(x) and str(x).replace(".", "").isdigit() else None
            ),
            "country": cleaned_df["Country"].astype(str),
            "is_cancelled": cleaned_df["is_cancelled"].astype(bool),
            "is_return": cleaned_df["is_return"].astype(bool),
            "is_guest": cleaned_df["is_guest"].astype(bool),
            "line_total": cleaned_df["LineTotal"].astype(float),
            "year": cleaned_df["Year"].astype(int),
            "month": cleaned_df["Month"].astype(int),
            "year_month": cleaned_df["YearMonth"].astype(str),
            "day_of_week": cleaned_df["DayOfWeek"].astype(str),
            "hour": cleaned_df["Hour"].astype(int),
        }
    )

    with eng.begin() as conn:
        if truncate:
            conn.execute(text("TRUNCATE TABLE cleaned_transactions RESTART IDENTITY;"))

    df_sql.to_sql(
        "cleaned_transactions",
        eng,
        if_exists="append",
        index=False,
        chunksize=chunksize,
        method="multi",
    )
    logger.info(f"Loaded {len(df_sql):,} records into cleaned_transactions")
    return len(df_sql)


def load_rfm_to_db(
    rfm_df: pd.DataFrame,
    engine: Optional[Engine] = None,
    truncate: bool = True,
) -> int:
    """Load RFM segmentation results into customer_rfm table."""
    eng = engine or get_engine()

    df_sql = pd.DataFrame(
        {
            "customer_id": rfm_df["CustomerID"].astype(str),
            "recency_days": rfm_df["Recency"].astype(int),
            "frequency_orders": rfm_df["Frequency"].astype(int),
            "monetary_spend": rfm_df["Monetary"].astype(float),
            "r_score": rfm_df["R_Score"].astype(int),
            "f_score": rfm_df["F_Score"].astype(int),
            "m_score": rfm_df["M_Score"].astype(int),
            "rfm_score": rfm_df["RFM_Score"].astype(str),
            "customer_segment": rfm_df["Segment"].astype(str),
            "first_purchase_date": pd.to_datetime(rfm_df["FirstPurchaseDate"])
            if "FirstPurchaseDate" in rfm_df.columns
            else None,
            "last_purchase_date": pd.to_datetime(rfm_df["LastPurchaseDate"])
            if "LastPurchaseDate" in rfm_df.columns
            else None,
        }
    )

    with eng.begin() as conn:
        if truncate:
            conn.execute(text("TRUNCATE TABLE customer_rfm;"))

    df_sql.to_sql(
        "customer_rfm",
        eng,
        if_exists="append",
        index=False,
        chunksize=2000,
        method="multi",
    )
    logger.info(f"Loaded {len(df_sql):,} customer records into customer_rfm")
    return len(df_sql)


def load_audit_log_to_db(
    audit_df: pd.DataFrame,
    engine: Optional[Engine] = None,
    truncate: bool = True,
) -> int:
    """Load cleaning audit trail into cleaning_audit_log table."""
    eng = engine or get_engine()

    df_sql = pd.DataFrame(
        {
            "step_name": audit_df["step_name"].astype(str),
            "description": audit_df["description"].astype(str),
            "records_before": audit_df["records_before"].astype(int),
            "records_after": audit_df["records_after"].astype(int),
            "records_impacted": audit_df["records_impacted"].astype(int),
            "pct_impacted": audit_df["pct_impacted"].astype(float),
            "notes": audit_df["notes"].fillna("").astype(str),
        }
    )

    with eng.begin() as conn:
        if truncate:
            conn.execute(text("TRUNCATE TABLE cleaning_audit_log RESTART IDENTITY;"))

    df_sql.to_sql(
        "cleaning_audit_log",
        eng,
        if_exists="append",
        index=False,
        method="multi",
    )
    logger.info(f"Loaded {len(df_sql):,} steps into cleaning_audit_log")
    return len(df_sql)


def populate_database(
    raw_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    audit_df: pd.DataFrame,
    rfm_df: Optional[pd.DataFrame] = None,
    engine: Optional[Engine] = None,
) -> bool:
    """Full database loading orchestrator."""
    eng = engine or get_engine()
    is_ok, msg = check_db_connection(eng)
    if not is_ok:
        logger.error(f"Cannot populate database: {msg}")
        return False

    init_db(eng)
    load_raw_to_db(raw_df, eng)
    load_cleaned_to_db(cleaned_df, eng)
    load_audit_log_to_db(audit_df, eng)
    if rfm_df is not None:
        load_rfm_to_db(rfm_df, eng)
    logger.info("Database population complete.")
    return True
