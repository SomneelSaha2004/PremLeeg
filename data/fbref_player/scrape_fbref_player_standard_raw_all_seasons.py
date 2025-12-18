#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import random
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL_TPL = "https://fbref.com/en/comps/9/{season}/stats/{season}-Premier-League-Stats#all_stats_standard"


def season_str_for(start_year: int) -> str:
    """1993 -> 1993-1994, 2025 -> 2025-2026"""
    return f"{start_year}-{start_year + 1}"


@dataclass
class SeasonScrapeLog:
    season: str
    url: str
    ok: bool
    rows: int
    cols: int
    out_path: str
    error: Optional[str] = None


def setup_driver(headless: bool) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    # Keep Chrome stable
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    driver = webdriver.Chrome(options=options)
    return driver


def scrape_one_season_raw(driver: webdriver.Chrome, url: str, timeout_s: int) -> pd.DataFrame:
    driver.get(url)

    wait = WebDriverWait(driver, timeout_s)
    table = wait.until(EC.presence_of_element_located((By.ID, "stats_standard")))

    # Extract just the table markup and let pandas parse it
    table_html = table.get_attribute("outerHTML")
    df = pd.read_html(io.StringIO(table_html))[0]  # raw df (may include MultiIndex headers)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=1993)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--out-dir", type=str, default="data/fbref/players_raw")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--timeout", type=int, default=25, help="Seconds to wait for table")
    ap.add_argument("--sleep-min", type=float, default=2.0)
    ap.add_argument("--sleep-max", type=float, default=5.0)
    ap.add_argument("--force", action="store_true", help="Re-scrape even if file exists")
    args = ap.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    logs: List[SeasonScrapeLog] = []

    driver = setup_driver(args.headless)
    try:
        for start_year in range(args.start_year, args.end_year + 1):
            season = season_str_for(start_year)
            url = URL_TPL.format(season=season)

            season_dir = out_root / season
            season_dir.mkdir(parents=True, exist_ok=True)
            out_path = season_dir / f"player_standard_stats_raw_{season}.csv"

            if out_path.exists() and not args.force:
                logs.append(SeasonScrapeLog(
                    season=season,
                    url=url,
                    ok=True,
                    rows=-1,
                    cols=-1,
                    out_path=str(out_path),
                    error="SKIPPED (already exists)",
                ))
                print(f"[SKIP] {season} -> {out_path}")
                time.sleep(random.uniform(args.sleep_min, args.sleep_max))
                continue

            try:
                df = scrape_one_season_raw(driver, url, timeout_s=args.timeout)

                # Save raw. If columns are MultiIndex, pandas will write them as multiple header rows.
                df.to_csv(out_path, index=False)

                logs.append(SeasonScrapeLog(
                    season=season,
                    url=url,
                    ok=True,
                    rows=int(df.shape[0]),
                    cols=int(df.shape[1]),
                    out_path=str(out_path),
                ))
                print(f"[OK] {season}: rows={df.shape[0]} cols={df.shape[1]} -> {out_path}")

            except Exception as e:
                logs.append(SeasonScrapeLog(
                    season=season,
                    url=url,
                    ok=False,
                    rows=0,
                    cols=0,
                    out_path=str(out_path),
                    error=str(e),
                ))
                print(f"[FAIL] {season}: {e}")

            # polite delay
            time.sleep(random.uniform(args.sleep_min, args.sleep_max))

    finally:
        driver.quit()

    manifest_path = out_root / "scrape_manifest.csv"
    pd.DataFrame([asdict(x) for x in logs]).to_csv(manifest_path, index=False)
    print(f"\nManifest: {manifest_path}")

    ok = sum(1 for x in logs if x.ok and (x.error is None or "SKIPPED" not in x.error))
    fail = sum(1 for x in logs if not x.ok)
    skip = sum(1 for x in logs if x.ok and x.error and "SKIPPED" in x.error)
    print(f"Summary: ok={ok}, failed={fail}, skipped={skip}")


if __name__ == "__main__":
    main()
