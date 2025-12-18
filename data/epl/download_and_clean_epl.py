#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from dateutil import parser as dtparser

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season_code}/E0.csv"

# Allowlist: ONLY keep non-odds / match-stat columns that are useful for MVP.
SOURCE_KEEP_COLS = [
    "Div", "Date", "Time", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR",
    "HTHG", "HTAG", "HTR",
    "Referee",
    "HS", "AS", "HST", "AST",
    "HF", "AF", "HC", "AC",
    "HY", "AY", "HR", "AR",
]

# Map football-data column names to our stable warehouse schema names.
RENAME_MAP = {
    "Div": "div",
    "Date": "match_date",
    "Time": "kickoff_time",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "Referee": "referee",
    "FTHG": "ft_home_goals",
    "FTAG": "ft_away_goals",
    "FTR": "ft_result",
    "HTHG": "ht_home_goals",
    "HTAG": "ht_away_goals",
    "HTR": "ht_result",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HC": "home_corners",
    "AC": "away_corners",
    "HY": "home_yellow",
    "AY": "away_yellow",
    "HR": "home_red",
    "AR": "away_red",
}

# Final column order for cleaned CSVs
FINAL_COLS = [
    "match_id",
    "season_code",
    "season_start",
    "div",
    "match_date",
    "kickoff_time",
    "home_team",
    "away_team",
    "referee",
    "ft_home_goals",
    "ft_away_goals",
    "ft_result",
    "ht_home_goals",
    "ht_away_goals",
    "ht_result",
    "home_shots",
    "away_shots",
    "home_shots_on_target",
    "away_shots_on_target",
    "home_fouls",
    "away_fouls",
    "home_corners",
    "away_corners",
    "home_yellow",
    "away_yellow",
    "home_red",
    "away_red",
]

INT_COLS = [
    "ft_home_goals", "ft_away_goals",
    "ht_home_goals", "ht_away_goals",
    "home_shots", "away_shots",
    "home_shots_on_target", "away_shots_on_target",
    "home_fouls", "away_fouls",
    "home_corners", "away_corners",
    "home_yellow", "away_yellow",
    "home_red", "away_red",
]


def season_code_for(start_year: int) -> str:
    """1993 -> 9394, 1999 -> 9900, 2009 -> 0910, 2025 -> 2526"""
    yy = start_year % 100
    zz = (start_year + 1) % 100
    return f"{yy:02d}{zz:02d}"


def parse_date(s: str) -> Optional[pd.Timestamp]:
    if pd.isna(s) or str(s).strip() == "":
        return None
    try:
        # football-data is typically day-first
        dt = dtparser.parse(str(s), dayfirst=True, fuzzy=True)
        return pd.Timestamp(dt.date())
    except Exception:
        return None


def parse_time(s: str) -> Optional[str]:
    if pd.isna(s) or str(s).strip() == "":
        return None
    s = str(s).strip()
    # Keep "HH:MM" if it looks like time
    if len(s) >= 4 and ":" in s:
        hhmm = s[:5]
        return hhmm
    return None


def compute_match_id(season_code: str, match_date: str, home: str, away: str) -> str:
    key = f"{season_code}|{match_date}|{home}|{away}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def download_csv(url: str, dest: Path, timeout: int = 45) -> Tuple[bool, Optional[int], Optional[str]]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "epl-downloader/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 404:
            return False, 404, None
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True, r.status_code, None
    except Exception as e:
        return False, None, str(e)


def clean_one_season(raw_csv_path: Path, season_code: str, season_start: int) -> pd.DataFrame:
    # Only read the columns we actually need, ignore extra fields
    # Use on_bad_lines to handle rows with inconsistent field counts
    # Use latin-1 encoding for older football-data.co.uk files
    try:
        df = pd.read_csv(
            raw_csv_path,
            usecols=lambda c: c in SOURCE_KEEP_COLS,
            on_bad_lines="warn",
            encoding="latin-1",  # handles non-UTF-8 chars like 0xa0
        )
    except TypeError:
        # Fallback for older pandas versions (<1.3) that don't have on_bad_lines
        df = pd.read_csv(
            raw_csv_path,
            usecols=lambda c: c in SOURCE_KEEP_COLS,
            error_bad_lines=False,
            warn_bad_lines=True,
            encoding="latin-1",
        )

    # Ensure all keep columns exist (older seasons might miss some stats columns)
    for c in SOURCE_KEEP_COLS:
        if c not in df.columns:
            df[c] = pd.NA

    df = df[SOURCE_KEEP_COLS].rename(columns=RENAME_MAP)

    # Normalize strings
    for c in ["div", "home_team", "away_team", "referee", "ft_result", "ht_result"]:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()

    # Parse dates / time
    df["match_date"] = df["match_date"].apply(parse_date)
    df["kickoff_time"] = df["kickoff_time"].apply(parse_time)

    # Coerce ints (nullable integer)
    for c in INT_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    # Add season fields
    df["season_code"] = season_code
    df["season_start"] = season_start

    # Drop rows with missing essentials
    df = df.dropna(subset=["match_date", "home_team", "away_team"])

    # Compute match_id (stable)
    df["match_id"] = df.apply(
        lambda r: compute_match_id(
            season_code,
            r["match_date"].strftime("%Y-%m-%d"),
            str(r["home_team"]),
            str(r["away_team"]),
        ),
        axis=1,
    )

    # Reorder and keep stable columns
    for c in FINAL_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[FINAL_COLS].copy()

    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=1993, help="First season start year (default: 1993)")
    ap.add_argument("--end-year", type=int, default=2025, help="Last season start year (default: 2025 -> 2025/26)")
    ap.add_argument("--out-dir", type=str, default="data/epl", help="Output folder")
    ap.add_argument("--sleep", type=float, default=0.25, help="Sleep between downloads")
    ap.add_argument("--skip-existing", action="store_true", help="Skip raw download if already present")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    clean_dir = out_dir / "clean"

    all_clean: List[pd.DataFrame] = []
    download_log: List[Dict[str, object]] = []

    for start_year in range(args.start_year, args.end_year + 1):
        code = season_code_for(start_year)
        url = BASE_URL.format(season_code=code)

        raw_path = raw_dir / code / "E0.csv"
        clean_path = clean_dir / code / "pl_matches.csv"

        # Download
        if args.skip_existing and raw_path.exists() and raw_path.stat().st_size > 0:
            ok, status, err = True, None, None
        else:
            ok, status, err = download_csv(url, raw_path)

        download_log.append({
            "season_code": code,
            "season_start": start_year,
            "url": url,
            "raw_path": str(raw_path),
            "ok": ok,
            "http_status": status,
            "error": err,
        })

        if not ok:
            # Some seasons might be missing; keep going.
            print(f"[WARN] {code}: download failed (status={status}, err={err})")
            time.sleep(args.sleep)
            continue

        # Clean
        df_clean = clean_one_season(raw_path, code, start_year)
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(clean_path, index=False)
        all_clean.append(df_clean)

        print(f"[OK] {code}: rows={len(df_clean)} -> {clean_path}")
        time.sleep(args.sleep)

    # Combine
    if all_clean:
        combined = pd.concat(all_clean, ignore_index=True)
        combined_path = clean_dir / "pl_matches_all.csv"
        combined.to_csv(combined_path, index=False)
        print(f"\nCombined CSV: {combined_path} (rows={len(combined)})")

    # Write download manifest
    manifest_path = out_dir / "download_manifest.csv"
    pd.DataFrame(download_log).to_csv(manifest_path, index=False)
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
