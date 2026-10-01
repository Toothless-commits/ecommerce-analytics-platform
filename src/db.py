"""
Database management module.
Provides SQLAlchemy connection pooling, health checks, schema initialization,
and parameterized query execution with graceful fallback.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from src.config import DATABASE_URL, SQL_DIR

logger = logging.getLogger(__name__)

_ENGINE: Optional[Engine] = None


def get_engine(db_url: Optional[str] = None) -> Engine:
    """
    Get or create SQLAlchemy engine singleton with connection pooling.
    """
    global _ENGINE
    if _ENGINE is not None and db_url is None:
        return _ENGINE

    url = db_url or DATABASE_URL
    _ENGINE = create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    return _ENGINE


def check_db_connection(engine: Optional[Engine] = None) -> Tuple[bool, str]:
    """
    Test whether the PostgreSQL database is reachable.
    Returns (is_connected, message).
    """
    eng = engine or get_engine()
    try:
        with eng.connect() as conn:
            result = conn.execute(text("SELECT version();")).scalar()
            return True, f"Connected to PostgreSQL: {result.split()[0]} {result.split()[1]}"
    except OperationalError as e:
        msg = str(e.orig) if hasattr(e, "orig") else str(e)
        logger.warning(f"Database connection failed: {msg}")
        return False, f"PostgreSQL unavailable: {msg}"
    except Exception as e:
        logger.warning(f"Database check failed: {e}")
        return False, str(e)


def init_db(engine: Optional[Engine] = None, schema_file: Optional[str] = None) -> bool:
    """
    Initialize database schema by executing sql/schema.sql.
    """
    eng = engine or get_engine()
    schema_path = SQL_DIR / (schema_file or "schema.sql")

    if not schema_path.exists():
        logger.error(f"Schema file not found at {schema_path}")
        return False

    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    try:
        with eng.begin() as conn:
            # Split and execute individual statements
            statements = [s.strip() for s in sql_script.split(";") if s.strip()]
            for stmt in statements:
                conn.execute(text(stmt))
        logger.info(f"Database schema initialized successfully from {schema_path}")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database schema: {e}")
        return False


def execute_query(
    query_sql: str,
    params: Optional[Dict[str, Any]] = None,
    engine: Optional[Engine] = None,
) -> pd.DataFrame:
    """
    Execute a parameterized SQL query and return results as a Pandas DataFrame.
    """
    eng = engine or get_engine()
    with eng.connect() as conn:
        df = pd.read_sql_query(text(query_sql), conn, params=params or {})
    return df
