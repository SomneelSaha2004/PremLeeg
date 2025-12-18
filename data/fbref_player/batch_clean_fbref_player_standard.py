#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Your original identity rename map (expects flattened "level_0 + header" columns)
RENAME_MAP = {
    "Unnamed: 0_level_0_Rk": "rk",
    "Unnamed: 1_level_0_Player": "player",
    "Unnamed: 2_level_0_Nation": "nation",
    "Unnamed: 3_level_0_Pos": "pos",
    "Unnamed: 4_level_0_Squad": "squad",
    "Unnamed: 5_level_0_Age": "age_raw",
    "Unnamed: 6_level_0_Born": "born_year",
    # Matches column index can vary slightly; we also detect it dynamically below
    "Unnamed: 36_level_0_Matches": "matches_link_text",
}

# Minimal required columns for our pipeline (same as yours)
REQUIRED = [
    "rk", "player", "nation", "pos", "squad", "age_raw", "born_year",
    "Playing Time_MP", "Playing Time_Starts", "Playing Time_Min", "Playing Time_90s",
]

# Numeric columns (same as yours)
NUMERIC_COLS = [
    "Playing Time_MP", "Playing Time_Starts", "Playing Time_Min", "Playing Time_90s",
    "Performance_Gls", "Performance_Ast", "Performance_G+A", "Performance_G-PK",
    "Performance_PK", "Performance_PKatt", "Performance_CrdY", "Performance_CrdR",
    "Expected_xG", "Expected_npxG", "Expected_xAG", "Expected_npxG+xAG",
    "Progression_PrgC", "Progression_PrgP", "Progression_PrgR",
    "Per 90 Minutes_Gls", "Per 90 Minutes_Ast", "Per 90 Minutes_G+A",
    "Per 90 Minutes_G-PK", "Per 90 Minutes_G+A-PK",
    "Per 90 Minutes_xG", "Per 90 Minutes_xAG", "Per 90 Minutes_xG+xAG",
    "Per 90 Minutes_npxG", "Per 90 Minutes_npxG+xAG",
]


def parse_age(age_raw: pd.Series) -> pd.DataFrame:
    """
    FBref age format: '25-057' => 25 years, 57 days.
    """
    s = age_raw.astype(str).str.strip()
    parts = s.str.split("-", n=1, expand=True)
    out = pd.DataFrame(index=age_raw.index)
    out["age_years"] = pd.to_numeric(parts[0], errors="coerce")
    out["age_days"] = pd.to_numeric(parts[1] if parts.shape[1] > 1 else None, errors="coerce")
    return out


def season_start_from_season(season: str) -> Optional[int]:
    # "1993-1994" -> 1993
    try:
        return int(season.split("-")[0])
    except Exception:
        return None


def read_fbref_two_header_csv(csv_path: Path) -> pd.DataFrame:
    """
    Your raw CSVs have:
      row1: group labels (Playing Time, Performance, ...)
      row2: column labels (MP, Starts, ...)
    So we read with header=[0,1] and flatten to:
      "Playing Time_MP", "Performance_Gls", "Unnamed: 0_level_0_Rk", ...
    """
    df = pd.read_csv(csv_path, header=[0, 1])

    if not isinstance(df.columns, pd.MultiIndex):
        # Unexpected, but fallback
        return pd.read_csv(csv_path)

    flat_cols: List[str] = []
    for lvl0, lvl1 in df.columns:
        a = "" if pd.isna(lvl0) else str(lvl0).strip()
        b = "" if pd.isna(lvl1) else str(lvl1).strip()
        # Join exactly like pandas flattening conventions you were using before
        if a and b:
            flat_cols.append(f"{a}_{b}")
        elif b:
            flat_cols.append(b)
        else:
            flat_cols.append(a)

    df.columns = flat_cols
    return df


def detect_matches_column(df: pd.DataFrame) -> Optional[str]:
    # Look for the flattened identity column that ends with "_Matches"
    for c in df.columns:
        if str(c).strip().endswith("_Matches"):
            return c
    # or plain "Matches"
    if "Matches" in df.columns:
        return "Matches"
    return None


def clean_one_file(in_path: Path, season: str) -> Dict[str, object]:
    raw_df = read_fbref_two_header_csv(in_path)
    raw_rows = len(raw_df)

    # Rename identity columns to your stable names
    df = raw_df.rename(columns=RENAME_MAP)

    # Dynamically handle Matches column (in case its Unnamed index differs)
    matches_col = detect_matches_column(raw_df)
    if matches_col and matches_col in df.columns:
        df = df.rename(columns={matches_col: "matches_link_text"})

    # Must have rk after renaming (or it will all go null)
    if "rk" not in df.columns:
        # Give a clear error rather than silently producing all-null output
        raise ValueError(
            f"Could not find 'rk' after header flatten+rename. "
            f"Example columns: {list(raw_df.columns)[:12]}"
        )

    # Drop repeated header rows inside tbody (rk should be numeric)
    df["rk_num"] = pd.to_numeric(df["rk"], errors="coerce")
    header_rows = int(df["rk_num"].isna().sum())
    df = df[df["rk_num"].notna()].copy()
    df = df.drop(columns=["rk"]).rename(columns={"rk_num": "rk"})

    # Drop Matches link-text column (not data)
    if "matches_link_text" in df.columns:
        df = df.drop(columns=["matches_link_text"])

    # Required column check
    missing = [c for c in REQUIRED if c not in df.columns]

    # Parse age
    age_df = parse_age(df["age_raw"]) if "age_raw" in df.columns else pd.DataFrame(index=df.index)
    df = pd.concat([df, age_df], axis=1)

    # Numeric coercion
    numeric_present = [c for c in NUMERIC_COLS if c in df.columns]
    for c in numeric_present:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "born_year" in df.columns:
        df["born_year"] = pd.to_numeric(df["born_year"], errors="coerce")

    # Add season metadata (useful for global table)
    df.insert(0, "season", season)
    ss = season_start_from_season(season)
    df.insert(1, "season_start", ss if ss is not None else pd.NA)

    # Sanity checks
    issues: Dict[str, int] = {}
    for c in ["player", "squad", "pos"]:
        if c in df.columns:
            issues[f"null_{c}"] = int(df[c].isna().sum())

    if "Playing Time_Starts" in df.columns and "Playing Time_MP" in df.columns:
        issues["starts_gt_mp"] = int((df["Playing Time_Starts"] > df["Playing Time_MP"]).sum())
    else:
        issues["starts_gt_mp"] = 0

    if "Playing Time_Min" in df.columns:
        issues["negative_minutes"] = int((df["Playing Time_Min"] < 0).sum())
    else:
        issues["negative_minutes"] = 0

    if "player" in df.columns and "squad" in df.columns:
        issues["dup_player_squad"] = int(df.duplicated(subset=["season", "player", "squad"]).sum())
    else:
        issues["dup_player_squad"] = 0

    return {
        "df": df,
        "raw_rows": raw_rows,
        "header_rows_removed": header_rows,
        "missing_required": missing,
        **issues,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--raw-root",
        required=True,
        help="Root dir containing season folders, e.g. .../data/fbref/players_raw",
    )
    ap.add_argument(
        "--out-root",
        default="data/fbref/players_clean",
        help="Output root dir for cleaned files/reports",
    )
    ap.add_argument(
        "--pattern",
        default="player_standard_stats_raw_*.csv",
        help="Filename glob inside each season folder",
    )
    ap.add_argument(
        "--combine",
        action="store_true",
        help="Write a combined ALL seasons CSV to out-root (can be large)",
    )
    args = ap.parse_args()

    raw_root = Path(args.raw_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    seasons = sorted([p for p in raw_root.iterdir() if p.is_dir()])

    manifest_rows: List[Dict[str, object]] = []
    all_clean: List[pd.DataFrame] = []

    for season_dir in seasons:
        season = season_dir.name  # "1993-1994"
        files = list(season_dir.glob(args.pattern))
        if not files:
            continue

        in_path = files[0]
        season_out_dir = out_root / season
        season_out_dir.mkdir(parents=True, exist_ok=True)

        out_csv = season_out_dir / f"pl_player_standard_stats_cleaned_{season}.csv"
        report_txt = season_out_dir / f"validation_report_{season}.txt"
        dups_csv = season_out_dir / f"duplicates_player_squad_{season}.csv"

        try:
            res = clean_one_file(in_path, season)
            df = res["df"]

            # Write cleaned CSV
            df.to_csv(out_csv, index=False)

            # Write report
            report_lines = []
            report_lines.append(f"Input file: {in_path}")
            report_lines.append(f"Raw rows (excluding the 2 header rows): {res['raw_rows']:,}")
            report_lines.append(f"Removed repeated header rows inside body: {res['header_rows_removed']:,}")
            report_lines.append(f"Final rows: {len(df):,}")
            report_lines.append(f"Columns: {len(df.columns):,}")
            report_lines.append("")
            report_lines.append(f"Missing required columns: {res['missing_required'] if res['missing_required'] else 'None'}")
            report_lines.append("")
            report_lines.append("Sanity checks:")
            report_lines.append(f"- null_player: {res['null_player']}")
            report_lines.append(f"- null_squad: {res['null_squad']}")
            report_lines.append(f"- null_pos: {res['null_pos']}")
            report_lines.append(f"- starts_gt_mp: {res['starts_gt_mp']}")
            report_lines.append(f"- negative_minutes: {res['negative_minutes']}")
            report_lines.append(f"- dup_player_squad: {res['dup_player_squad']}")
            report_lines.append("")
            report_lines.append("Top squads by row count:")
            if "squad" in df.columns:
                for squad, cnt in df["squad"].value_counts().head(10).items():
                    report_lines.append(f"  - {squad}: {cnt}")
            report_txt.write_text("\n".join(report_lines), encoding="utf-8")

            # Write duplicates (if any)
            if res["dup_player_squad"] > 0:
                df[df.duplicated(subset=["season", "player", "squad"], keep=False)] \
                    .sort_values(["squad", "player"]) \
                    .to_csv(dups_csv, index=False)

            manifest_rows.append({
                "season": season,
                "in_path": str(in_path),
                "ok": True,
                "raw_rows": res["raw_rows"],
                "removed_header_rows": res["header_rows_removed"],
                "out_rows": len(df),
                "out_cols": len(df.columns),
                "missing_required": ";".join(res["missing_required"]) if res["missing_required"] else "",
                "starts_gt_mp": res["starts_gt_mp"],
                "negative_minutes": res["negative_minutes"],
                "dup_player_squad": res["dup_player_squad"],
                "out_csv": str(out_csv),
                "report_txt": str(report_txt),
                "error": "",
            })

            all_clean.append(df)
            print(f"[OK] {season}: rows={len(df)} -> {out_csv}")

        except Exception as e:
            manifest_rows.append({
                "season": season,
                "in_path": str(in_path),
                "ok": False,
                "raw_rows": 0,
                "removed_header_rows": 0,
                "out_rows": 0,
                "out_cols": 0,
                "missing_required": "",
                "starts_gt_mp": 0,
                "negative_minutes": 0,
                "dup_player_squad": 0,
                "out_csv": str(out_csv),
                "report_txt": str(report_txt),
                "error": repr(e),
            })
            print(f"[FAIL] {season}: {repr(e)}")

    # Write manifest
    manifest_path = out_root / "clean_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
    print(f"\nManifest: {manifest_path}")

    # Optional combined
    if args.combine and all_clean:
        combined = pd.concat(all_clean, ignore_index=True)
        combined_path = out_root / "pl_player_standard_stats_cleaned_ALL.csv"
        combined.to_csv(combined_path, index=False)
        print(f"[OK] Combined: {combined_path} (rows={len(combined):,})")


if __name__ == "__main__":
    main()
