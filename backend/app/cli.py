#!/usr/bin/env python3
import argparse
import sys
from typing import Iterable

from .agent.pipeline import run_pipeline


def iter_questions(path: str) -> Iterable[str]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            q = line.strip()
            if q:
                yield q


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NL->SQL questions from a file")
    parser.add_argument("file", help="Path to a text file with one question per line")
    parser.add_argument("--limit", type=int, default=100, help="Max rows to return")
    args = parser.parse_args()

    for q in iter_questions(args.file):
        print(f"\nQuestion: {q}")
        res = run_pipeline(q, limit=args.limit)
        print("SQL:\n" + res.sql)
        print("\nResults:")
        if res.rows:
            # Pretty print small tables
            headers = res.rows[0].keys()
            print("\t".join(headers))
            for row in res.rows:
                print("\t".join(str(row[h]) for h in headers))
        else:
            print("<no rows>")
        if res.explanation:
            print("\nExplanation:\n" + res.explanation)
    return 0


if __name__ == "__main__":
    sys.exit(main())
