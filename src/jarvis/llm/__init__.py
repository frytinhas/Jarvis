"""Local model provider abstractions."""

from jarvis.llm.llama_cpp import LlamaCppProvider
from jarvis.llm.provider import LLMProvider

__all__ = ["LLMProvider", "LlamaCppProvider"]
