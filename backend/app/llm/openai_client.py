from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI


@dataclass
class LLMResponse:
    text: str


_SQL_CLEAN_RE = re.compile(r"```sql|```", re.IGNORECASE)
_JSON_CLEAN_RE = re.compile(r"```json\s*|```", re.IGNORECASE)


class OpenAILLM:
    def __init__(self, model: Optional[str] = None):
        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _messages(self, prompt: str):
        return [
            {
                "role": "system",
                "content": (
                    "You generate Postgres SQL only. "
                    "Never include explanations, markdown, or code fences."
                ),
            },
            {"role": "user", "content": prompt},
        ]

    def generate_sql(self, prompt: str) -> LLMResponse:
        messages = self._messages(prompt)
        text: str

        try:
            # Newer SDKs (>=1.0) expose the Responses API
            resp = self.client.responses.create(
                model=self.model,
                temperature=0.2,
                input=messages,
            )
            text = (resp.output_text or "").strip()
        except AttributeError:
            # Fall back to chat completions for older SDKs / compatibility
            chat = self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                messages=messages,
            )
            choice = chat.choices[0]
            # pydantic models expose .message.content
            if hasattr(choice, "message") and getattr(choice.message, "content", None):
                text = choice.message.content
            elif hasattr(choice, "text") and choice.text:
                text = choice.text
            else:
                text = ""
            text = text.strip()

        text = _SQL_CLEAN_RE.sub("", text).strip()
        return LLMResponse(text=text)

    def generate_text(self, prompt: str) -> LLMResponse:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a careful data analyst. "
                    "You must only use the provided data and must not make up facts."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            resp = self.client.responses.create(
                model=self.model,
                temperature=0.1,
                input=messages,
            )
            text = (resp.output_text or "").strip()
        except AttributeError:
            chat = self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                messages=messages,
            )
            choice = chat.choices[0]
            if hasattr(choice, "message") and getattr(choice.message, "content", None):
                text = choice.message.content
            elif hasattr(choice, "text") and choice.text:
                text = choice.text
            else:
                text = ""
            text = text.strip()

        return LLMResponse(text=text)

    def generate_json(self, prompt: str) -> LLMResponse:
        """Generate structured JSON output for multi-query generation."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate valid JSON only. "
                    "Never include explanations, markdown fences, or any text outside the JSON structure."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            resp = self.client.responses.create(
                model=self.model,
                temperature=0.3,  # Slightly higher for query diversity
                input=messages,
            )
            text = (resp.output_text or "").strip()
        except AttributeError:
            chat = self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                messages=messages,
            )
            choice = chat.choices[0]
            if hasattr(choice, "message") and getattr(choice.message, "content", None):
                text = choice.message.content
            elif hasattr(choice, "text") and choice.text:
                text = choice.text
            else:
                text = ""
            text = text.strip()

        # Clean up any markdown fences
        text = _JSON_CLEAN_RE.sub("", text).strip()
        return LLMResponse(text=text)

