from __future__ import annotations

import os
from typing import Any, Dict, List

import psycopg


def _get_db_url() -> str:
    url = os.getenv("DATABASE_URL_READONLY") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL(_READONLY) not set")
    return url


def execute_select(sql: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Execute read-only SQL and return rows as dicts.

    Note: Ensure the provided credentials are read-only on the database.
    """
    params = params or {}
    with psycopg.connect(_get_db_url()) as conn:
        conn.execute("SET statement_timeout TO '15s'")
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
