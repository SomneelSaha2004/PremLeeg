from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .agent.pipeline import AgentPipeline
from .models.types import QueryRequest, QueryResponse

app = FastAPI(title="PL Data Copilot API")
pipeline = AgentPipeline()


@app.get("/health")
def health():
    return {"ok": True}


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

    return QueryResponse(sql=out.sql, columns=out.columns, rows=out.rows, summary=out.summary)
