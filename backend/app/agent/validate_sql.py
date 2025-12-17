from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Set

import sqlglot
from sqlglot import exp


BANNED_REGEX = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do)\b",
    re.IGNORECASE,
)

ALLOWED_TABLES: Set[str] = {
    "pl_matches",
    "pl_team_match",
    "pl_season_table",
}

DEFAULT_LIMIT = 200


@dataclass
class ValidatedSQL:
    sql: str


class SQLValidationError(ValueError):
    pass


def _ensure_single_statement(sql: str) -> None:
    parsed = sqlglot.parse(sql, read="postgres")
    if len(parsed) != 1:
        raise SQLValidationError("Only a single SQL statement is allowed.")


def _ensure_select_only(sql: str) -> None:
    if BANNED_REGEX.search(sql):
        raise SQLValidationError("Only read-only SELECT queries are allowed.")


def _ensure_allowed_tables(sql: str) -> None:
    parsed = sqlglot.parse_one(sql, read="postgres")
    tables = {t.name for t in parsed.find_all(exp.Table)}
    # Allow schema-qualified names too; we only care about the table identifier
    if not tables:
        return
    unknown = {t for t in tables if t not in ALLOWED_TABLES}
    if unknown:
        raise SQLValidationError(f"Query references non-allowed tables/views: {sorted(unknown)}")


def _ensure_limit(sql: str, limit: int = DEFAULT_LIMIT) -> str:
    parsed = sqlglot.parse_one(sql, read="postgres")
    # If it's a SELECT or a WITH...SELECT, enforce LIMIT
    select = parsed.find(exp.Select)
    if select is None:
        # If model returns something weird, just block it
        raise SQLValidationError("Only SELECT queries are allowed.")
    if select.args.get("limit") is None:
        select.set("limit", exp.Limit(this=exp.Literal.number(limit)))
        return parsed.sql(dialect="postgres")
    return sql


def validate_and_patch_sql(sql: str, limit: int = DEFAULT_LIMIT) -> ValidatedSQL:
    sql = (sql or "").strip().rstrip(";")
    if not sql:
        raise SQLValidationError("Empty SQL.")
    _ensure_single_statement(sql)
    _ensure_select_only(sql)
    _ensure_allowed_tables(sql)
    sql = _ensure_limit(sql, limit=limit)
    return ValidatedSQL(sql=sql)
