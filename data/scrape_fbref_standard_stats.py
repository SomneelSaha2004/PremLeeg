#!/usr/bin/env python3
from __future__ import annotations

import re
import time
import random
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

URL = "https://fbref.com/en/squads/18bb7c10/2025-2026/c9/Arsenal-Stats-Premier-League"

HEADERS = {
    # Be polite; don't pretend to be a browser with fake UA strings
    "User-Agent": "pl-data-copilot/0.1 (educational project; contact: you@example.com)"
}

OUT_PATH = Path("data/fbref/arsenal_standard_stats_2025_2026.csv")


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    # polite delay (important for Sports Reference sites)
    time.sleep(random.uniform(1.5, 3.0))
    return r.text


def strip_html_comments(html: str) -> str:
    # FBref sometimes wraps tables inside <!-- ... -->
    # Removing comment markers makes tables visible to pandas read_html
    return re.sub(r"<!--|-->", "", html)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    FBref tables sometimes have multi-index headers; flatten them.
    Example: ('Playing Time', 'MP') -> 'MP'
    """
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join([str(x).strip() for x in col if str(x).strip() and str(x) != "nan"]).strip("_")
            for col in df.columns
        ]
    else:
        df.columns = [str(c).strip() for c in df.columns]
    return df


def find_standard_stats_table(html: str) -> pd.DataFrame:
    """
    Prefer table id 'stats_standard' if present.
    If not found, fall back to heuristics.
    """
    # Try extracting the specific table via regex (fast + robust)
    m = re.search(r'(<table[^>]+id="stats_standard"[^>]*>.*?</table>)', html, flags=re.S)
    if m:
        table_html = m.group(1)
        df = pd.read_html(table_html)[0]
        return df

    # Fallback: parse all tables and pick one that looks like "Standard Stats"
    tables = pd.read_html(html)
    for df in tables:
        df = normalize_columns(df)

        cols = set(df.columns.astype(str))
        # typical columns in Standard Stats tables
        must_have = {"Player", "Nation", "Pos", "Age", "MP", "Starts", "Min"}
        if must_have.issubset(cols):
            return df

    raise RuntimeError("Could not locate the Standard Stats table on the page.")


def clean_standard_stats(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)

    # Drop repeated header rows (sometimes 'Player' repeats inside data)
    if "Player" in df.columns:
        df = df[df["Player"].notna()]
        df = df[df["Player"].astype(str).str.strip().ne("Player")]

    # Remove squad total rows if present
    if "Player" in df.columns:
        df = df[~df["Player"].astype(str).str.contains("Squad Total|Opponent Total", case=False, na=False)]

    # Strip whitespace from string columns
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()

    return df.reset_index(drop=True)


def main() -> None:
    html = fetch_html(URL)
    html = strip_html_comments(html)

    df = find_standard_stats_table(html)
    df = clean_standard_stats(df)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"[OK] Saved {len(df)} rows to {OUT_PATH}")
    print("Columns:", list(df.columns))
    print(df.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
