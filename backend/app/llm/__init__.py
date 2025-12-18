"""LLM providers.

Project standard:
- Use LangChain as the primary integration.
- Keep `openai_client.py` for legacy/direct-SDK usage.
"""

# Default LLM used by the app/pipeline
from .langchain_client import OpenAILLM, LLMResponse  # noqa: F401

# Legacy implementation kept for compatibility/debugging
from .openai_client import OpenAILLM as LegacyOpenAILLM  # noqa: F401