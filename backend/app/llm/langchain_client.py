from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


@dataclass
class LLMResponse:
    text: str


_SQL_CLEAN_RE = re.compile(r"```sql|```", re.IGNORECASE)
_JSON_CLEAN_RE = re.compile(r"```json\s*|```", re.IGNORECASE)


class OpenAILLM:
    """LangChain-backed LLM wrapper.

    This intentionally preserves the existing interface expected by the pipeline:
      - generate_sql(prompt) -> LLMResponse(text=...)
      - generate_text(prompt) -> LLMResponse(text=...)

    Configuration:
      - OPENAI_MODEL (default: gpt-4o-mini)
      - OPENAI_API_KEY is read by the OpenAI SDK underneath
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # Keep these defaults aligned with the existing behavior.
        self._sql_llm = ChatOpenAI(model=self.model, temperature=0.2)
        self._text_llm = ChatOpenAI(model=self.model, temperature=0.1)
        self._json_llm = ChatOpenAI(model=self.model, temperature=0.3)  # For multi-query JSON output

    def generate_sql(self, prompt: str) -> LLMResponse:
        msg = self._sql_llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You generate Postgres SQL only. "
                        "Never include explanations, markdown, or code fences."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )

        text = (getattr(msg, "content", "") or "").strip()
        text = _SQL_CLEAN_RE.sub("", text).strip()
        return LLMResponse(text=text)

    def generate_text(self, prompt: str) -> LLMResponse:
        msg = self._text_llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a careful data analyst. "
                        "You must only use the provided data and must not make up facts."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )

        text = (getattr(msg, "content", "") or "").strip()
        return LLMResponse(text=text)

    def generate_json(self, prompt: str) -> LLMResponse:
        """Generate structured JSON output for multi-query generation."""
        msg = self._json_llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You generate valid JSON only. "
                        "Never include explanations, markdown fences, or any text outside the JSON structure."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )

        text = (getattr(msg, "content", "") or "").strip()
        text = _JSON_CLEAN_RE.sub("", text).strip()
        return LLMResponse(text=text)
