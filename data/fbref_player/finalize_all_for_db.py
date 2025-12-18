#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


# Target DB schema (40 cols)
FINAL_COLS = [
    "season", "season_start", "rk", "player", "nation", "pos", "squad",
    "age_raw", "born_year", "age_years", "age_days",
    "playing_time_mp", "playing_time_starts", "playing_time_min", "playing_time_90s",
    "performance_gls", "performance_ast", "performance_g_plus_a", "performance_g_minus_pk",
    "performance_pk", "performance_pkatt", "performance_crdy", "performance_crdr",
    "expected_xg", "expected_npxg", "expected_xag", "expected_npxg_plus_xag",
    "progression_prgc", "progression_prgp", "progression_prgr",
    "per90_gls", "per90_ast", "per90_g_plus_a", "per90_g_minus_pk", "per90_g_plus_a_minus_pk",
    "per90_xg", "per90_xag", "per90_xg_plus_xag", "per90_npxg", "per90_npxg_plus_xag",
]

# If your combined file still has "FBref-ish" columns with spaces/+ signs,
# this normalizes them into DB-safe snake_case.
# (If your file is already snake_case, these will just be no-ops.)
RENAME_TO_DB = {
    "Playing Time_MP": "playing_time_mp",
    "Playing Time_Starts": "playing_time_starts",
    "Playing Time_Min": "playing_time_min",
    "Playing Time_90s": "playing_time_90s",

    "Performance_Gls": "performance_gls",
    "Performance_Ast": "performance_ast",
    "Performance_G+A": "performance_g_plus_a",
    "Performance_G-PK": "performance_g_minus_pk",
    "Performance_PK": "performance_pk",
    "Performance_PKatt": "performance_pkatt",
    "Performance_CrdY": "performance_crdy",
    "Performance_CrdR": "performance_crdr",

    "Expected_xG": "expected_xg",
    "Expected_npxG": "expected_npxg",
    "Expected_xAG": "expected_xag",
    "Expected_npxG+xAG": "expected_npxg_plus_xag",

    "Progression_PrgC": "progression_prgc",
    "Progression_PrgP": "progression_prgp",
    "Progression_PrgR": "progression_prgr",

    "Per 90 Minutes_Gls": "per90_gls",
    "Per 90 Minutes_Ast": "per90_ast",
    "Per 90 Minutes_G+A": "per90_g_plus_a",
    "Per 90 Minutes_G-PK": "per90_g_minus_pk",
    "Per 90 Minutes_G+A-PK": "per90_g_plus_a_minus_pk",
    "Per 90 Minutes_xG": "per90_xg",
    "Per 90 Minutes_xAG": "per90_xag",
    "Per 90 Minutes_xG+xAG": "per90_xg_plus_xag",
    "Per 90 Minutes_npxG": "per90_npxg",
    "Per 90 Minutes_npxG+xAG": "per90_npxg_plus_xag",
}

INT_COLS = {
    "season_start", "rk", "born_year", "age_years", "age_days",
    "playing_time_mp", "playing_time_starts", "playing_time_min",
    "performance_gls", "performance_ast", "performance_g_plus_a", "performance_g_minus_pk",
    "performance_pk", "performance_pkatt", "performance_crdy", "performance_crdr",
    "progression_prgc", "progression_prgp", "progression_prgr",
}

FLOAT_COLS = {
    "playing_time_90s",
    "expected_xg", "expected_npxg", "expected_xag", "expected_npxg_plus_xag",
    "per90_gls", "per90_ast", "per90_g_plus_a", "per90_g_minus_pk", "per90_g_plus_a_minus_pk",
    "per90_xg", "per90_xag", "per90_xg_plus_xag", "per90_npxg", "per90_npxg_plus_xag",
}

REQUIRED = {"season", "season_start", "player", "squad", "playing_time_mp", "playing_time_min"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_csv", required=True, help="Combined cleaned ALL seasons CSV")
    ap.add_argument("--out", default="pl_player_standard_stats_ALL_db.csv", help="DB-ready output CSV")
    ap.add_argument("--report", default="players_all_validation_report.txt", help="Validation report output")
    args = ap.parse_args()

    in_path = Path(args.in_csv)
    out_path = Path(args.out)
    report_path = Path(args.report)

    df = pd.read_csv(in_path, low_memory=False)

    # Normalize column names if needed
    df = df.rename(columns=RENAME_TO_DB)

    # Trim key strings
    for c in ["season", "player", "nation", "pos", "squad", "age_raw"]:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()

    # Coerce numeric types
    for c in INT_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in FLOAT_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Ensure all final columns exist; fill missing as NULLs
    for c in FINAL_COLS:
        if c not in df.columns:
            df[c] = pd.NA

    # Reorder to stable superset schema
    df = df[FINAL_COLS].copy()

    # Basic validations
    issues = {}
    issues["rows"] = len(df)
    issues["cols"] = len(df.columns)

    # Missing required (all-null)
    issues["missing_required_all_null"] = [c for c in REQUIRED if df[c].isna().all()]

    # Duplicates by (season, player, squad)
    issues["dup_season_player_squad"] = int(df.duplicated(subset=["season", "player", "squad"]).sum())

    # Starts <= MP check (if present)
    issues["starts_gt_mp"] = int(
        ((df["playing_time_starts"] > df["playing_time_mp"]) &
         df["playing_time_starts"].notna() & df["playing_time_mp"].notna()).sum()
    )

    # Negative minutes
    issues["negative_minutes"] = int(((df["playing_time_min"] < 0) & df["playing_time_min"].notna()).sum())

    # Write db-ready csv
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    # Write report
    lines = []
    lines.append(f"Input:  {in_path}")
    lines.append(f"Output: {out_path}")
    lines.append("")
    lines.append(f"Rows: {issues['rows']:,}")
    lines.append(f"Cols: {issues['cols']:,}")
    lines.append("")
    lines.append(f"Missing required (all-null): {issues['missing_required_all_null'] or 'None'}")
    lines.append(f"Duplicates (season,player,squad): {issues['dup_season_player_squad']}")
    lines.append(f"starts_gt_mp: {issues['starts_gt_mp']}")
    lines.append(f"negative_minutes: {issues['negative_minutes']}")
    lines.append("")
    lines.append("Null counts for key columns:")
    for c in ["season", "season_start", "player", "squad", "pos", "nation", "born_year"]:
        if c in df.columns:
            lines.append(f"- {c}: {int(df[c].isna().sum())}")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote:   {out_path}")
    print(f"[OK] Report:  {report_path}")
    print(f"[OK] Rows:    {len(df):,}")
    print(f"[OK] Dups:    {issues['dup_season_player_squad']}")


if __name__ == "__main__":
    main()
