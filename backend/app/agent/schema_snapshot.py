#!/usr/bin/env python3
"""
schema_snapshot.py (relation-centric)

Produces a compact schema snapshot optimized for:
- agent prompt context
- runtime LLM calls
- easy lookup by table/view

Default: only public schema.

Env vars:
  DATABASE_URL=...
  SCHEMAS="public,other"   (default "public")
  OUT="schema_snapshot.json"
  PRETTY=1                (default 1; set 0 to minify JSON)
  INCLUDE_INDEXDEF=0      (default 0; set 1 to include full CREATE INDEX text)
"""

import os
import re
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

import psycopg2


RELATIONS_SQL = """
SELECT
  n.nspname AS schema,
  c.relname AS name,
  c.relkind AS relkind,
  c.oid AS oid,
  c.reltuples::bigint AS row_estimate
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = ANY(%s)
  AND c.relkind IN ('r','p','v','m')
ORDER BY n.nspname, c.relname;
"""

COLUMNS_SQL = """
SELECT
  table_schema AS schema,
  table_name   AS name,
  ordinal_position AS ord,
  column_name  AS col,
  data_type    AS typ,
  (is_nullable = 'NO') AS not_null
FROM information_schema.columns
WHERE table_schema = ANY(%s)
ORDER BY table_schema, table_name, ordinal_position;
"""

VIEWS_SQL = """
SELECT
  n.nspname AS schema,
  c.relname AS name,
  pg_get_viewdef(c.oid, true) AS definition
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = ANY(%s)
  AND c.relkind IN ('v','m')
ORDER BY n.nspname, c.relname;
"""

INDEXES_SQL = """
SELECT
  schemaname AS schema,
  tablename  AS name,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname = ANY(%s)
ORDER BY schemaname, tablename, indexname;
"""


def parse_schemas() -> List[str]:
  raw = os.getenv("SCHEMAS", "public").strip()
  schemas = [s.strip() for s in raw.split(",") if s.strip()]
  return schemas or ["public"]


def fetchall(cur, sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
  cur.execute(sql, params)
  cols = [d[0] for d in cur.description]
  out: List[Dict[str, Any]] = []
  for row in cur.fetchall():
    out.append({cols[i]: row[i] for i in range(len(cols))})
  return out


def relkind_to_type(relkind: str) -> str:
  # pg_class.relkind
  # r=table, p=partitioned table, v=view, m=materialized view
  return {
    "r": "table",
    "p": "table",
    "v": "view",
    "m": "materialized_view",
  }.get(relkind, relkind)


_INDEX_RE = re.compile(
  r"""^CREATE\s+(?P<unique>UNIQUE\s+)?INDEX\s+.*?\s+ON\s+.*?\s+USING\s+(?P<method>\w+)\s*\((?P<cols>.*)\)\s*(?P<where>WHERE\s+.*)?$""",
  re.IGNORECASE | re.DOTALL
)

def _split_cols(cols_blob: str) -> List[str]:
  """
  Split the inside of (...) for index columns.
  Handles simple commas; tolerates expressions by tracking paren depth.
  """
  cols_blob = cols_blob.strip()
  if not cols_blob:
    return []
  out, buf, depth = [], [], 0
  for ch in cols_blob:
    if ch == "(":
      depth += 1
    elif ch == ")":
      depth = max(0, depth - 1)
    if ch == "," and depth == 0:
      out.append("".join(buf).strip())
      buf = []
    else:
      buf.append(ch)
  if buf:
    out.append("".join(buf).strip())
  return [c for c in out if c]


def parse_index(indexname: str, indexdef: str, include_def: bool) -> Dict[str, Any]:
  d: Dict[str, Any] = {"name": indexname}
  m = _INDEX_RE.match(indexdef.strip())
  if m:
    d["unique"] = bool(m.group("unique"))
    d["method"] = (m.group("method") or "").lower() or None
    d["cols"] = _split_cols(m.group("cols") or "")
    if m.group("where"):
      d["where"] = (m.group("where") or "").strip()
  else:
    # fallback when the regex doesn't match (rare but possible)
    d["unique"] = "CREATE UNIQUE INDEX" in indexdef.upper()
  if include_def:
    d["def"] = indexdef
  return d


def main() -> None:
  db_url = os.getenv("DATABASE_URL_READONLY")
  if not db_url:
    raise SystemExit(
      "Missing DATABASE."
    )

  include_schemas = parse_schemas()
  now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

  out_path = "schema_snapshot.json"
  pretty = 1
  include_indexdef = 1

  with psycopg2.connect(db_url) as conn:
    with conn.cursor() as cur:
      rels = fetchall(cur, RELATIONS_SQL, (include_schemas,))
      cols = fetchall(cur, COLUMNS_SQL, (include_schemas,))
      views = fetchall(cur, VIEWS_SQL, (include_schemas,))
      idxs = fetchall(cur, INDEXES_SQL, (include_schemas,))

  # Build relation-centric objects
  # Key: "schema.name"
  rel_map: Dict[str, Dict[str, Any]] = {}
  for r in rels:
    key = f"{r['schema']}.{r['name']}"
    rel_map[key] = {
      "schema": r["schema"],
      "name": r["name"],
      "type": relkind_to_type(r["relkind"]),
      "row_estimate": r["row_estimate"],
      "columns": [],
      "indexes": [],
    }

  # Attach columns (only for relations we care about)
  for c in cols:
    key = f"{c['schema']}.{c['name']}"
    obj = rel_map.get(key)
    if not obj:
      continue
    obj["columns"].append({
      "name": c["col"],
      "type": c["typ"],
      "not_null": bool(c["not_null"]),
      # ordinal usually not needed, but we keep stable order via query ORDER BY
    })

  # Attach view definitions
  for v in views:
    key = f"{v['schema']}.{v['name']}"
    obj = rel_map.get(key)
    if not obj:
      continue
    obj["definition"] = v["definition"]

  # Attach indexes
  for i in idxs:
    key = f"{i['schema']}.{i['name']}"
    obj = rel_map.get(key)
    if not obj:
      continue
    obj["indexes"].append(parse_index(i["indexname"], i["indexdef"], include_indexdef))

  # Final ordered list (stable, LLM-friendly)
  relations = [rel_map[k] for k in sorted(rel_map.keys())]

  snapshot = {
    "generated_at": now,
    "include_schemas": include_schemas,
    "stats": {
      "relations": len(relations),
      "tables": sum(1 for r in relations if r["type"] == "table"),
      "views": sum(1 for r in relations if r["type"] in ("view", "materialized_view")),
    },
    "relations": relations,
  }

  with open(out_path, "w", encoding="utf-8") as f:
    if pretty:
      json.dump(snapshot, f, indent=2, ensure_ascii=False)
    else:
      json.dump(snapshot, f, separators=(",", ":"), ensure_ascii=False)

  print(f"Wrote snapshot: {out_path}")
  print(json.dumps(snapshot["stats"], indent=2))


if __name__ == "__main__":
  main()
