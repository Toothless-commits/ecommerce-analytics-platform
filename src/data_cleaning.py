"""
Data cleaning and validation pipeline.
Implements documented, auditable rules to transform raw e-commerce transactions
into high-integrity analytical datasets without fabricating data.
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import AUDIT_LOG_PATH, CLEANED_CSV_PATH, CLEANED_PARQUET_PATH

logger = logging.getLogger(__name__)

# Known administrative / non-commercial merchandise stock codes
ADMIN_STOCK_CODES = {
    "POST",
    "D",
    "M",
    "C2",
    "BANK CHARGES",
    "PADS",
    "DOT",
    "CRUK",
    "AMAZONFEE",
    "B",
    "S",
}


@dataclass
class CleaningAuditStep:
    step_name: str
    description: str
    records_before: int
    records_after: int
    records_impacted: int
    pct_impacted: float
    notes: str


class DataCleaner:
    """
    Cleans raw transaction records with auditable steps and explicit accounting definitions.
    """

    def __init__(self, raw_df: pd.DataFrame):
        self.raw_df = raw_df.copy()
        self.cleaned_df = pd.DataFrame()
        self.audit_steps: List[CleaningAuditStep] = []
        self.summary_stats: Dict = {}

    def _log_step(
        self,
        step_name: str,
        description: str,
        df_before: pd.DataFrame,
        df_after: pd.DataFrame,
        notes: str = "",
    ):
        before_cnt = len(df_before)
        after_cnt = len(df_after)
        impacted = before_cnt - after_cnt
        pct = (impacted / before_cnt * 100) if before_cnt > 0 else 0.0

        step = CleaningAuditStep(
            step_name=step_name,
            description=description,
            records_before=before_cnt,
            records_after=after_cnt,
            records_impacted=impacted,
            pct_impacted=round(pct, 3),
            notes=notes,
        )
        self.audit_steps.append(step)
        logger.info(
            f"[{step_name}] {description} | Before: {before_cnt:,} -> After: {after_cnt:,} (Diff: {impacted:,}, {pct:.2f}%)"
        )

    def run_pipeline(
        self,
        remove_admin_codes: bool = True,
        remove_unidentified_customers: bool = False,
    ) -> Tuple[pd.DataFrame, List[CleaningAuditStep]]:
        """
        Execute full cleaning pipeline:
        1. Type normalization & whitespace trimming
        2. Exact duplicate removal
        3. Unit price validation (> 0)
        4. Administrative stock code tagging / filtering
        5. Cancellation & return identification
        6. Line total and temporal feature creation
        """
        df = self.raw_df.copy()
        initial_len = len(df)
        self._log_step(
            step_name="0_INITIAL",
            description="Raw dataset ingested into memory",
            df_before=df,
            df_after=df,
            notes=f"Total raw rows: {initial_len:,}",
        )

        # Step 1: Type normalization & string stripping
        step1_before = df.copy()
        df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
        df["StockCode"] = df["StockCode"].astype(str).str.strip()
        df["Description"] = df["Description"].fillna("").astype(str).str.strip()
        df["Country"] = df["Country"].fillna("Unspecified").astype(str).str.strip()

        # Parse InvoiceDate
        df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
        df = df[df["InvoiceDate"].notna()]

        # Ensure numeric Quantity and UnitPrice
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
        df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce").fillna(0.0).astype(float)

        self._log_step(
            step_name="1_TYPE_NORMALIZATION",
            description="Normalized data types, parsed datetime, trimmed strings",
            df_before=step1_before,
            df_after=df,
            notes="Invalid timestamps dropped if any.",
        )

        # Step 2: Remove Exact Duplicates
        step2_before = df.copy()
        dup_subset = [
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
        ]
        df = df.drop_duplicates(subset=dup_subset).reset_index(drop=True)
        self._log_step(
            step_name="2_EXACT_DUPLICATES",
            description="Removed exact duplicate transaction rows",
            df_before=step2_before,
            df_after=df,
            notes="Redundant records from system logging or transmission repeats.",
        )

        # Step 3: Filter non-positive UnitPrice
        # Note: UnitPrice <= 0 indicates internal inventory adjustments, free promos, or bad debt corrections
        step3_before = df.copy()
        zero_or_negative_price = df["UnitPrice"] <= 0
        df = df[~zero_or_negative_price].reset_index(drop=True)
        self._log_step(
            step_name="3_INVALID_PRICE",
            description="Removed transactions with UnitPrice <= 0.0",
            df_before=step3_before,
            df_after=df,
            notes="Filtered warehouse adjustments, lost inventory, and zero-price test lines.",
        )

        # Step 4: Tag & handle cancellations and returns
        # Cancelled invoices start with 'C' in UCI dataset, and Quantity is negative
        step4_before = df.copy()
        is_c_invoice = df["InvoiceNo"].str.upper().str.startswith("C")
        is_negative_qty = df["Quantity"] < 0

        df["is_cancelled"] = is_c_invoice | is_negative_qty
        df["is_return"] = df["is_cancelled"] & is_negative_qty

        # Quantity == 0 records
        df = df[df["Quantity"] != 0].reset_index(drop=True)
        self._log_step(
            step_name="4_ZERO_QUANTITY",
            description="Filtered lines with Quantity == 0",
            df_before=step4_before,
            df_after=df,
            notes="Tagged cancellation invoices ('C') and returns.",
        )

        # Step 5: Administrative Stock Codes
        step5_before = df.copy()
        stock_clean = df["StockCode"].str.upper()
        df["is_admin_code"] = stock_clean.isin(ADMIN_STOCK_CODES)

        if remove_admin_codes:
            df = df[~df["is_admin_code"]].reset_index(drop=True)
            self._log_step(
                step_name="5_ADMIN_STOCK_CODES",
                description="Filtered administrative codes (POST, D, M, BANK CHARGES, etc.)",
                df_before=step5_before,
                df_after=df,
                notes="Restricted dataset to retail merchandise sales.",
            )
        else:
            self._log_step(
                step_name="5_ADMIN_STOCK_CODES",
                description="Tagged administrative codes without filtering",
                df_before=step5_before,
                df_after=df,
                notes="Admin items preserved with flag.",
            )

        # Step 6: Customer ID Handling
        step6_before = df.copy()
        df["is_guest"] = df["CustomerID"].isna()

        # Format CustomerID consistently (float -> nullable int or clean string)
        df["CustomerID_Clean"] = df["CustomerID"].apply(
            lambda x: str(int(x)) if pd.notna(x) and str(x).replace(".", "").isdigit() else "GUEST"
        )

        if remove_unidentified_customers:
            df = df[~df["is_guest"]].reset_index(drop=True)
            self._log_step(
                step_name="6_GUEST_CHECKOUTS",
                description="Filtered unauthenticated guest transactions (null CustomerID)",
                df_before=step6_before,
                df_after=df,
                notes="Only registered customers retained.",
            )
        else:
            self._log_step(
                step_name="6_GUEST_CHECKOUTS",
                description="Preserved guest transactions tagged with is_guest=True",
                df_before=step6_before,
                df_after=df,
                notes="Guest checkouts retained for revenue accuracy, tagged for customer metrics.",
            )

        # Step 7: Derived Metrics and Temporal Features
        # Line Total:
        # For sales: Quantity * UnitPrice (> 0)
        # For returns: Quantity * UnitPrice (< 0, represents refunded value)
        df["LineTotal"] = df["Quantity"] * df["UnitPrice"]

        # Date aggregations
        df["Date"] = df["InvoiceDate"].dt.date
        df["Year"] = df["InvoiceDate"].dt.year
        df["Month"] = df["InvoiceDate"].dt.month
        df["YearMonth"] = df["InvoiceDate"].dt.to_period("M").astype(str)
        df["DayOfWeek"] = df["InvoiceDate"].dt.day_name()
        df["Hour"] = df["InvoiceDate"].dt.hour

        # Finalize
        self.cleaned_df = df
        self._generate_summary_stats()
        return self.cleaned_df, self.audit_steps

    def _generate_summary_stats(self):
        """Generate high-level data quality and audit statistics."""
        raw = self.raw_df
        clean = self.cleaned_df

        self.summary_stats = {
            "raw_total_records": len(raw),
            "cleaned_total_records": len(clean),
            "retention_rate_pct": round(len(clean) / len(raw) * 100, 2) if len(raw) > 0 else 0.0,
            "raw_missing_customer_ids": int(raw["CustomerID"].isna().sum()) if "CustomerID" in raw.columns else 0,
            "raw_missing_customer_id_pct": round(raw["CustomerID"].isna().mean() * 100, 2) if "CustomerID" in raw.columns else 0.0,
            "raw_cancelled_invoices": int(raw["InvoiceNo"].astype(str).str.startswith("C").sum()) if "InvoiceNo" in raw.columns else 0,
            "cleaned_sales_records": int((clean["Quantity"] > 0).sum()) if len(clean) > 0 else 0,
            "cleaned_return_records": int((clean["Quantity"] < 0).sum()) if len(clean) > 0 else 0,
            "cleaned_unique_customers": int(clean[~clean["is_guest"]]["CustomerID"].nunique()) if len(clean) > 0 else 0,
            "cleaned_unique_invoices": int(clean["InvoiceNo"].nunique()) if len(clean) > 0 else 0,
            "cleaned_countries_count": int(clean["Country"].nunique()) if len(clean) > 0 else 0,
            "date_min": str(clean["InvoiceDate"].min()) if len(clean) > 0 else "",
            "date_max": str(clean["InvoiceDate"].max()) if len(clean) > 0 else "",
        }

    def save_results(
        self,
        parquet_path: Path = CLEANED_PARQUET_PATH,
        csv_path: Path = CLEANED_CSV_PATH,
        audit_path: Path = AUDIT_LOG_PATH,
    ):
        """Save cleaned dataset and audit log to disk."""
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        self.cleaned_df.to_parquet(parquet_path, index=False)
        self.cleaned_df.to_csv(csv_path, index=False)

        audit_data = {
            "summary": self.summary_stats,
            "steps": [asdict(s) for s in self.audit_steps],
        }
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2)

        logger.info(f"Saved cleaned parquet to {parquet_path}")
        logger.info(f"Saved audit log to {audit_path}")

    def get_audit_df(self) -> pd.DataFrame:
        """Return audit steps as a display-ready Pandas DataFrame."""
        return pd.DataFrame([asdict(s) for s in self.audit_steps])


def clean_dataset(
    raw_df: pd.DataFrame,
    save: bool = True,
    remove_admin_codes: bool = True,
    remove_unidentified_customers: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Convenience functional interface for cleaning raw transactions.
    Returns:
        (cleaned_df, audit_df, summary_stats)
    """
    cleaner = DataCleaner(raw_df)
    cleaned_df, _ = cleaner.run_pipeline(
        remove_admin_codes=remove_admin_codes,
        remove_unidentified_customers=remove_unidentified_customers,
    )
    if save:
        cleaner.save_results()
    return cleaned_df, cleaner.get_audit_df(), cleaner.summary_stats
