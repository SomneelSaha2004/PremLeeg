from __future__ import annotations

# Golden questions for UI examples / guidelines.
# NOTE: these are NOT used in runtime prompting; they are for demo UX only.

GOLDEN = [
    {
        "question": "What's the biggest home win ever recorded in the Premier League?",
        "expected": "Multiple 9-0 wins: Man United 9-0 Ipswich Town (4 Mar 1995); Man United 9-0 Southampton (2 Feb 2021); Liverpool 9-0 AFC Bournemouth (27 Aug 2022). Should return ALL ties.",
        "tests": "TIE-SAFE pattern for home wins",
    },
    {
        "question": "What's the biggest away win in Premier League history?",
        "expected": "Southampton 0-9 Leicester City (25 Oct 2019). 9-goal margin.",
        "tests": "TIE-SAFE pattern for away wins",
    },
    {
        "question": "What is the highest-scoring match in Premier League history?",
        "expected": "Portsmouth 7-4 Reading (29 Sep 2007). 11 goals total.",
        "tests": "TIE-SAFE pattern for total goals",
    },
    {
        "question": "What's the highest-scoring draw ever in the Premier League?",
        "expected": "West Brom 5-5 Man United (19 May 2013). 10 goals total.",
        "tests": "TIE-SAFE pattern with draw filter",
    },
    {
        "question": "Which team collected the most points in a single Premier League season?",
        "expected": "100 points by Manchester City (2017/18). Must use v_team_season_summary or pl_season_table, NOT player views.",
        "tests": "COMPLETE-SEASON filter + correct view selection (team not player)",
    },
]
