from __future__ import annotations

import asyncio
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agent.pipeline import AgentPipeline
from .agent.golden_questions import GOLDEN
from .models.types import QueryRequest, QueryResponse

app = FastAPI(title="PL Data Copilot API")
pipeline = AgentPipeline()


# Global exception handler to catch all errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print("=" * 60)
    print("UNHANDLED EXCEPTION:")
    print("=" * 60)
    print(tb)
    print("=" * 60)
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "traceback": tb,
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/schema")
def get_schema():
    """Return a DB schema snapshot for the frontend dashboard."""
    repo_root = Path(__file__).resolve().parents[2]
    snapshot_path = repo_root / "schema_snapshot.json"
    if not snapshot_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error_code": "schema_snapshot_missing", "message": "schema_snapshot.json not found"},
        )
    import json

    return json.loads(snapshot_path.read_text(encoding="utf-8"))


@app.get("/api/golden-prompts")
def get_golden_prompts(limit: int = 5):
    limit = max(0, min(int(limit), len(GOLDEN)))
    return {
        "items": [
            {
                "question": item["question"],
                "expected": item.get("expected"),
                "tests": item.get("tests"),
            }
            for item in GOLDEN[:limit]
        ]
    }


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    try:
        if req.multi_query:
            # Use 3-query diversity mode with parallel execution
            out = await pipeline.run_multi_query(
                req.question,
                summarize=req.summarize,
                include_rows=req.include_rows,
                raise_on_error=True,
            )
            # Extract queries_attempted from trace
            queries_attempted = None
            if out.trace:
                for t in out.trace:
                    if isinstance(t, dict) and "queries_attempted" in t:
                        queries_attempted = t["queries_attempted"]
                        break
        else:
            # Standard single-query mode
            out = pipeline.run(
                req.question,
                summarize=req.summarize,
                include_rows=req.include_rows,
                raise_on_error=True,
            )
            queries_attempted = None
    except Exception as exc:
        # Print full stack trace for debugging
        print("=" * 60)
        print("QUERY ERROR - Full Stack Trace:")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        
        # Map validation/DB errors to 422 to avoid 500s for model mistakes
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "query_error",
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        ) from exc

    return QueryResponse(
        sql=out.sql,
        columns=out.columns,
        rows=out.rows,
        summary=out.summary,
        retry_token=out.retry_token,
        retry_reason=out.retry_reason,
        attempt_count=out.attempt_count,
        trace=out.trace,
        queries_attempted=queries_attempted,
    )


@app.post("/api/query", response_model=QueryResponse)
async def api_query(req: QueryRequest):
    return await query(req)
