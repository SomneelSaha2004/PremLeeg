from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent.pipeline import AgentPipeline
from .agent.golden_questions import GOLDEN
from .models.types import QueryRequest, QueryResponse

app = FastAPI(title="PL Data Copilot API")
pipeline = AgentPipeline()


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
def query(req: QueryRequest):
    try:
        out = pipeline.run(
            req.question,
            summarize=req.summarize,
            include_rows=req.include_rows,
            raise_on_error=True,
        )
    except Exception as exc:
        # Map validation/DB errors to 422 to avoid 500s for model mistakes
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "query_error",
                "message": str(exc),
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
    )


@app.post("/api/query", response_model=QueryResponse)
def api_query(req: QueryRequest):
    return query(req)
