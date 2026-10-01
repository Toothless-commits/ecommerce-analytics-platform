"""
Configuration module for E-Commerce Analytics Platform.
Loads environment variables and sets up directory paths.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Data directories
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
SQL_DIR = BASE_DIR / "sql"

# File paths
RAW_ZIP_PATH = RAW_DATA_DIR / "online_retail.zip"
RAW_EXCEL_PATH = RAW_DATA_DIR / "Online Retail.xlsx"
RAW_PARQUET_PATH = RAW_DATA_DIR / "raw_transactions.parquet"
CLEANED_PARQUET_PATH = PROCESSED_DATA_DIR / "cleaned_transactions.parquet"
CLEANED_CSV_PATH = PROCESSED_DATA_DIR / "cleaned_transactions.csv"
SAMPLE_CSV_PATH = SAMPLE_DATA_DIR / "online_retail_sample.csv"
AUDIT_LOG_PATH = PROCESSED_DATA_DIR / "cleaning_audit_log.json"

# UCI Dataset URL
UCI_DATASET_ZIP_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"

# Database Configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_analytics")

# Construct SQLAlchemy database URL
if DB_PASSWORD:
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Ensure required directories exist
def init_directories():
    """Ensure all required data directories exist."""
    for path in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, SAMPLE_DATA_DIR, SQL_DIR]:
        path.mkdir(parents=True, exist_ok=True)

init_directories()
