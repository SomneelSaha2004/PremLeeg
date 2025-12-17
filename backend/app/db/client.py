from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import psycopg


@dataclass
class QueryResult:
    columns: List[str]
    rows: List[Dict[str, Any]]


class PostgresClient:
    """
    Safe-ish DB runner:
    - Uses DATABASE_URL_READONLY
    - Sets statement_timeout per-connection
    - Returns rows as list-of-dicts
    """

    def __init__(self, dsn: Optional[str] = None, statement_timeout_ms: int = 5000):
        self.dsn = dsn or os.environ["DATABASE_URL_READONLY"]
        self.statement_timeout_ms = statement_timeout_ms

    def run_select(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> QueryResult:
        params = params or tuple()
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            # Hard timeout at DB level
            with conn.cursor() as cur:
                cur.execute(f"set statement_timeout = {int(self.statement_timeout_ms)};")
                cur.execute(sql, params)

                # Some SELECTs might return no rows
                if cur.description is None:
                    return QueryResult(columns=[], rows=[])

                cols = [d.name for d in cur.description]
                data = cur.fetchall()

        rows = [dict(zip(cols, r)) for r in data]
        return QueryResult(columns=cols, rows=rows)
