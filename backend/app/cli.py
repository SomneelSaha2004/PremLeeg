from __future__ import annotations

import argparse
import json

from .agent.pipeline import AgentPipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", type=str, required=True)
    ap.add_argument("--max-rows", type=int, default=20)
    ap.add_argument("--no-summary", action="store_true", help="Skip LLM summarization")
    ap.add_argument("--no-rows", action="store_true", help="Omit rows from CLI output")
    args = ap.parse_args()

    pipe = AgentPipeline()
    out = pipe.run(
        args.question,
        summarize=not args.no_summary,
        include_rows=not args.no_rows,
    )

    print("\n=== SQL ===")
    print(out.sql)

    if out.summary:
        print("\n=== SUMMARY ===")
        print(out.summary)

    if out.rows:
        print("\n=== ROWS (sample) ===")
        print(json.dumps(out.rows[: args.max_rows], indent=2, default=str))


if __name__ == "__main__":
    main()
