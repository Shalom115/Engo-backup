"""
LLM provider abstraction.

The rest of the codebase only ever talks to LLMProvider.
Swapping providers (Anthropic -> OpenAI -> local) = one env var change.
Nothing else in the system touches a vendor-specific SDK.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import os


class LLMProvider(ABC):
    """Abstract LLM interface. All concrete providers must implement this."""

    @abstractmethod
    def complete(
        self,
        system: Union[str, List[Dict[str, Any]]],
        user: str,
        max_tokens: int = 1024,
    ) -> str:
        """Single-turn completion. Returns the model's text response."""
        ...

    @abstractmethod
    def complete_full(
        self,
        system: Union[str, List[Dict[str, Any]]],
        user: str,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """Same as complete() but returns usage info alongside the text:
        {text, input_tokens, output_tokens, cache_read_input_tokens,
        cache_creation_input_tokens}."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class AnthropicProvider(LLMProvider):
    """Concrete Anthropic Claude implementation."""

    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system, user: str, max_tokens: int = 1024) -> str:
        return self.complete_full(system, user, max_tokens)["text"]

    def complete_full(self, system, user: str, max_tokens: int = 1024) -> Dict[str, Any]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        usage = response.usage
        return {
            "text": response.content[0].text,
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "cache_read_input_tokens": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            "cache_creation_input_tokens": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        }

    @property
    def model_name(self) -> str:
        return self._model


def get_llm_provider(model: Optional[str] = None) -> LLMProvider:
    """
    Factory: read env, return configured provider. Single point of vendor selection.

    Args:
        model: optional model override. If None, reads ANTHROPIC_MODEL env var
               (defaults to claude-sonnet-4-6). Pass explicitly for pipelines
               that need a different model (e.g. HyDE uses claude-haiku-4-5).
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
        effective_model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        return AnthropicProvider(api_key=api_key, model=effective_model)

    raise NotImplementedError(
        f"LLM_PROVIDER='{provider}' not implemented yet. "
        f"Add a new class extending LLMProvider in this file and wire it in here."
    )
