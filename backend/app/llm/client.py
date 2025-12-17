from __future__ import annotations

from typing import Any, Dict

from ..agent.prompts import SYSTEM_PROMPT


class SQLLLM:
    """Minimal placeholder LLM wrapper.

    For MVP scaffolding, returns a safe stub query so the pipeline is runnable
    before wiring up a local model like SQLCoder via llama-cpp-python.
    """

    def __init__(self, **_: Any) -> None:
        self.system_prompt = SYSTEM_PROMPT

    def generate_sql(self, question: str, schema_context: Dict[str, Any], limit: int | None = 100) -> str:
        # TODO: integrate SQLCoder-7B-2 via llama-cpp-python
        lim = limit or 100
        # Provide a deterministic stub to exercise the rest of the pipeline
        return f"SELECT 'LLM not yet configured' AS message, '{question}' AS question LIMIT {lim}"
