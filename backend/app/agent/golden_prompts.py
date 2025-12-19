"""Golden query runner for manual verification.

Sends each question to the /query API and prints SQL, summary, and row samples.
Expected answers are documented for quick eyeballing; no automated asserts here.
Set API_URL env var to point at the running FastAPI service (default http://localhost:8000/query).
"""

import json
import os
from typing import List, Dict

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000/query")

# Golden questions with expected human answers (ASCII only)
GOLDEN: List[Dict[str, str]] = [
    {
        "question": "Biggest PL home win ever?",
        "expected": "9-0 (Man United vs Ipswich, 4 Mar 1995); 9-0 (Man United vs Southampton, 2 Feb 2021); 9-0 (Liverpool vs Bournemouth, 27 Aug 2022).",
    },
    {
        "question": "Biggest PL away win ever?",
        "expected": "Southampton 0-9 Leicester City (25 Oct 2019).",
    },
    {
        "question": "Highest-scoring PL match ever?",
        "expected": "Portsmouth 7-4 Reading (29 Sep 2007).",
    },
    {
        "question": "Highest-scoring PL draw ever?",
        "expected": "West Brom 5-5 Manchester United (19 May 2013).",
    },
    {
        "question": "Highest PL single-match attendance ever?",
        "expected": "83,222 at Wembley Stadium, Tottenham vs Arsenal (10 Feb 2018).",
    },
    {
        "question": "Highest PL season average attendance ever?",
        "expected": "75,821 at Old Trafford, Manchester United (2006/07).",
    },
    {
        "question": "Most points in a PL season (club) and who did it?",
        "expected": "100 by Manchester City (2017/18).",
    },
    {
        "question": "Most goals scored in a PL season (club) and who did it?",
        "expected": "106 by Manchester City (2017/18).",
    },
    {
        "question": "Fewest goals conceded in a PL season (club) and who did it?",
        "expected": "15 by Chelsea (2004/05).",
    },
    {
        "question": "Most goals conceded in a PL season (club) and who did it?",
        "expected": "104 by Sheffield United (2023/24).",
    },
    {
        "question": "Most wins in a PL season (club) and who did it?",
        "expected": "32 by Manchester City (2017/18 and 2018/19) and Liverpool (2019/20).",
    },
    {
        "question": "Longest PL winning streak (consecutive wins) and who did it?",
        "expected": "18 by Manchester City (Aug-Dec 2017) and Liverpool (Oct 2019-Feb 2020).",
    },
    {
        "question": "Longest PL unbeaten run and who did it?",
        "expected": "49 by Arsenal (May 2003-Oct 2004).",
    },
    {
        "question": "Fewest points in a PL season (club) and who did it?",
        "expected": "11 by Derby County (2007/08).",
    },
    {
        "question": "Most yellow cards by a club in a single PL season?",
        "expected": "105 by Chelsea (2023/24).",
    },
    {
        "question": "Most red cards by a club in a single PL season?",
        "expected": "9 by Sunderland (2009/10) and 9 by QPR (2011/12).",
    },
    {
        "question": "Most goals by a player in a single PL season?",
        "expected": "36 by Erling Haaland (2022/23).",
    },
    {
        "question": "Most assists by a player in a single PL season?",
        "expected": "20 by Thierry Henry (2002/03) and 20 by Kevin De Bruyne (2019/20).",
    },
    {
        "question": "Most goal involvements (goals + assists) by a player in a PL season?",
        "expected": "47 by Andy Cole (1993/94), 47 by Alan Shearer (1993/94), 47 by Mohamed Salah (2024/25).",
    },
    {
        "question": "Most PL goals for a single club (player + club + total)?",
        "expected": "213 by Harry Kane (Tottenham Hotspur, 2013/14-2022/23).",
    },
]


def run_all():
    print(f"Using API_URL={API_URL}")
    for idx, item in enumerate(GOLDEN, start=1):
        q = item["question"]
        expected = item["expected"]
        print("\n" + "=" * 80)
        print(f"[{idx}] Question: {q}")
        print(f"Expected: {expected}")

        try:
            resp = requests.post(
                API_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps({"question": q, "include_rows": True, "summarize": True}),
                timeout=10,
            )
        except Exception as exc:  # network or other errors
            print(f"Error: {exc}")
            continue

        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}: {resp.text}")
            continue

        payload = resp.json()
        print("SQL:")
        print(payload.get("sql"))

        summary = payload.get("summary", "")
        if summary:
            print("Summary:")
            print(summary)

        rows = payload.get("rows") or []
        if rows:
            print("Rows (sample):")
            print(json.dumps(rows[:5], indent=2, default=str))


if __name__ == "__main__":
    run_all()
