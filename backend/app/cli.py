from __future__ import annotations

import argparse
import json

from .agent.pipeline import AgentPipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", type=str, required=True)
    ap.add_argument("--max-rows", type=int, default=20)
    args = ap.parse_args()

    pipe = AgentPipeline()
    out = pipe.run(args.question)

    print("\n=== SQL ===")
    print(out.sql)

    print("\n=== SUMMARY ===")
    print(out.summary)

    if out.rows:
        print("\n=== ROWS (sample) ===")
        print(json.dumps(out.rows[: args.max_rows], indent=2, default=str))


if __name__ == "__main__":
    main()
