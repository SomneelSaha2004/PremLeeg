from __future__ import annotations

import re

WRITE_KEYWORDS = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COMMENT|MERGE)\b", re.IGNORECASE)
SELECT_START = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE)
SEMI = re.compile(r";+")
LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)


def validate_and_sanitize(sql: str, default_limit: int = 100) -> str:
    """Enforce a conservative read-only policy and ensure a LIMIT.

    Rules:
      - Single statement (no multiple semicolons)
      - Starts with SELECT or WITH
      - Reject write keywords
      - Ensure a numeric LIMIT (append if missing)
    """
    if not SELECT_START.search(sql):
        raise ValueError("Only SELECT/WITH queries are allowed")

    # Single statement: strip trailing semicolons and ensure no additional ones inside
    sql = sql.strip()
    # If multiple semicolons exist, reject
    if len(SEMI.findall(sql)) > 1:
        raise ValueError("Multiple statements are not allowed")
    # Remove a single trailing semicolon if present
    sql = re.sub(r";\s*$", "", sql)

    if WRITE_KEYWORDS.search(sql):
        raise ValueError("Write operations are not allowed")

    # Enforce LIMIT
    m = LIMIT_RE.search(sql)
    if m:
        try:
            n = int(m.group(1))
            if n <= 0:
                raise ValueError("LIMIT must be positive")
        except ValueError as e:  # noqa: PERF203
            raise ValueError("LIMIT must be a positive integer") from e
        return sql

    # Append LIMIT if missing
    return f"{sql}\nLIMIT {int(default_limit)}"
