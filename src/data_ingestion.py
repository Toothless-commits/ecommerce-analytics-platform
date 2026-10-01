"""
Data ingestion module.
Handles downloading, caching, and loading UCI Online Retail dataset
as well as user-uploaded files and sample demo datasets.
"""

import io
import logging
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from src.config import (
    CLEANED_PARQUET_PATH,
    RAW_DATA_DIR,
    RAW_EXCEL_PATH,
    RAW_PARQUET_PATH,
    RAW_ZIP_PATH,
    SAMPLE_CSV_PATH,
    SAMPLE_DATA_DIR,
    UCI_DATASET_ZIP_URL,
    init_directories,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EXPECTED_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]


def _normalize_and_cache(df: pd.DataFrame, target_path: Path = RAW_PARQUET_PATH) -> pd.DataFrame:
    """Standardize column names, types, and cache to parquet."""
    df = standardize_columns(df)
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str)
    df["Description"] = df["Description"].fillna("").astype(str)
    df["Country"] = df["Country"].fillna("Unspecified").astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype("int32")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce").fillna(0.0).astype("float64")
    df.to_parquet(target_path, index=False)
    logger.info(f"Cached normalized dataset to {target_path} ({len(df):,} rows)")
    return df


def download_uci_dataset(force: bool = False) -> Path:
    """
    Download the UCI Online Retail dataset zip and extract Online Retail.xlsx.
    Converts to parquet for high-speed subsequent loads.
    """
    init_directories()

    if not force and RAW_PARQUET_PATH.exists():
        logger.info(f"Using cached raw parquet at {RAW_PARQUET_PATH}")
        return RAW_PARQUET_PATH

    if not force and RAW_EXCEL_PATH.exists():
        logger.info(f"Found existing raw Excel at {RAW_EXCEL_PATH}. Converting to parquet...")
        df = pd.read_excel(RAW_EXCEL_PATH, engine="openpyxl")
        _normalize_and_cache(df, RAW_PARQUET_PATH)
        return RAW_PARQUET_PATH

    logger.info(f"Downloading UCI dataset from {UCI_DATASET_ZIP_URL}...")
    req = urllib.request.Request(
        UCI_DATASET_ZIP_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read()

    with open(RAW_ZIP_PATH, "wb") as f:
        f.write(content)
    logger.info(f"Saved zip file ({len(content):,} bytes) to {RAW_ZIP_PATH}")

    # Extract Excel file
    with zipfile.ZipFile(RAW_ZIP_PATH, "r") as zf:
        excel_names = [n for n in zf.namelist() if n.endswith(".xlsx")]
        if not excel_names:
            raise FileNotFoundError("No .xlsx file found in downloaded zip archive.")
        extracted_name = excel_names[0]
        logger.info(f"Extracting '{extracted_name}' to {RAW_DATA_DIR}...")
        zf.extract(extracted_name, RAW_DATA_DIR)
        target_path = RAW_DATA_DIR / extracted_name
        if target_path != RAW_EXCEL_PATH and target_path.exists():
            target_path.rename(RAW_EXCEL_PATH)

    logger.info(f"Reading {RAW_EXCEL_PATH} with openpyxl...")
    df = pd.read_excel(RAW_EXCEL_PATH, engine="openpyxl")
    _normalize_and_cache(df, RAW_PARQUET_PATH)
    return RAW_PARQUET_PATH


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dataframe column names to canonical schema."""
    col_map = {}
    lower_expected = {c.lower(): c for c in EXPECTED_COLUMNS}
    for col in df.columns:
        clean_col = str(col).strip().replace(" ", "").replace("_", "")
        for exp_lower, exp_canonical in lower_expected.items():
            if clean_col.lower() == exp_lower.lower():
                col_map[col] = exp_canonical
                break
    df = df.rename(columns=col_map)
    return df


def load_raw_data(source: Optional[Union[str, Path, io.BytesIO]] = None) -> pd.DataFrame:
    """
    Load raw transaction data from a file path, BytesIO stream, or cached location.
    Prioritizes:
    1. Explicit source path / stream
    2. RAW_PARQUET_PATH
    3. RAW_EXCEL_PATH
    4. SAMPLE_CSV_PATH
    """
    init_directories()

    if source is not None:
        if isinstance(source, io.BytesIO) or hasattr(source, "read"):
            try:
                # Try reading as CSV first, fallback to Excel
                df = pd.read_csv(source)
            except Exception:
                if hasattr(source, "seek"):
                    source.seek(0)
                df = pd.read_excel(source, engine="openpyxl")
        else:
            p = Path(source)
            if p.suffix.lower() == ".parquet":
                df = pd.read_parquet(p)
            elif p.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(p, engine="openpyxl")
            else:
                df = pd.read_csv(p, encoding="utf-8", low_memory=False)
        return standardize_columns(df)

    if RAW_PARQUET_PATH.exists():
        logger.info(f"Loading raw data from parquet: {RAW_PARQUET_PATH}")
        df = pd.read_parquet(RAW_PARQUET_PATH)
        return standardize_columns(df)

    if RAW_EXCEL_PATH.exists():
        logger.info(f"Loading raw data from Excel: {RAW_EXCEL_PATH}")
        df = pd.read_excel(RAW_EXCEL_PATH, engine="openpyxl")
        return _normalize_and_cache(df, RAW_PARQUET_PATH)

    if SAMPLE_CSV_PATH.exists():
        logger.info(f"Loading fallback demo sample from: {SAMPLE_CSV_PATH}")
        df = pd.read_csv(SAMPLE_CSV_PATH)
        return standardize_columns(df)

    # If nothing exists locally, download the dataset
    logger.info("No local data found. Initiating automated dataset download...")
    parquet_path = download_uci_dataset()
    df = pd.read_parquet(parquet_path)
    return standardize_columns(df)


def create_sample_dataset(
    raw_df: pd.DataFrame, n_customers: int = 400, output_path: Path = SAMPLE_CSV_PATH
) -> pd.DataFrame:
    """
    Create a realistic, self-contained sample dataset for instant zero-config demo runs.
    Samples full transaction histories for a subset of customers to preserve RFM integrity,
    plus a proportion of guest checkouts and cancellations.
    """
    init_directories()
    raw_df = standardize_columns(raw_df)

    # 1. Select identified customers
    identified = raw_df[raw_df["CustomerID"].notna()]
    unique_custs = identified["CustomerID"].unique()
    sampled_custs = pd.Series(unique_custs).sample(
        n=min(n_customers, len(unique_custs)), random_state=42
    )
    cust_transactions = identified[identified["CustomerID"].isin(sampled_custs)]

    # 2. Sample guest checkout rows (~25% proportion to match original dataset)
    unidentified = raw_df[raw_df["CustomerID"].isna()]
    n_guest = int(len(cust_transactions) * 0.25)
    guest_sample = unidentified.sample(n=min(n_guest, len(unidentified)), random_state=42)

    sample_df = pd.concat([cust_transactions, guest_sample], ignore_index=True)
    sample_df = sample_df.sort_values("InvoiceDate").reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_df.to_csv(output_path, index=False)
    logger.info(
        f"Generated sample dataset with {len(sample_df):,} rows ({sample_df['CustomerID'].nunique()} unique customers) at {output_path}"
    )
    return sample_df


if __name__ == "__main__":
    download_uci_dataset()
    raw = load_raw_data()
    create_sample_dataset(raw)
