"""
app/ai/llm_factory.py — LLMClient protocol and provider factory.

Usage:
    from app.ai.llm_factory import get_llm_client, LLMClient, LLMResponse

    client: LLMClient = get_llm_client()
    response = await client.generate(prompt="...", system="...")

The factory reads settings.LLM_PROVIDER at call time:
  - "ollama"  → OllamaClient (default)
  - "claude"  → ClaudeClient (requires ANTHROPIC_API_KEY)

If LLM_PROVIDER=claude but ANTHROPIC_API_KEY is missing, a warning is logged
and the factory falls back to OllamaClient rather than crashing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable

logger = logging.getLogger("ai_coach.llm_factory")


# ── Shared response dataclass ─────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LLMResponse:
    """
    Provider-agnostic LLM generation response.

    Drop-in compatible with OllamaResponse — same fields plus optional
    cache token counters populated by ClaudeClient.

    Attributes:
        content: generated text
        prompt_tokens: tokens in the prompt (input)
        completion_tokens: tokens in the completion (output)
        total_tokens: sum of prompt + completion tokens
        response_time_ms: wall-clock generation time in milliseconds
        model_used: model identifier string
        cache_read_tokens: Anthropic prompt-cache read tokens (Claude only)
        cache_write_tokens: Anthropic prompt-cache write tokens (Claude only)
    """

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_ms: int
    model_used: str
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


# ── LLMClient protocol ────────────────────────────────────────────────────────

@runtime_checkable
class LLMClient(Protocol):
    """
    Structural protocol for LLM clients.

    Any class with matching generate() and stream_generate() signatures
    satisfies this protocol (OllamaClient, ClaudeClient, test stubs).
    """

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate a completion for the given prompt."""
        ...

    async def stream_generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream completion tokens for the given prompt."""
        ...


# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm_client() -> LLMClient:
    """
    Return the configured LLM client based on settings.LLM_PROVIDER.

    Decision logic:
      1. LLM_PROVIDER == "claude" AND ANTHROPIC_API_KEY is set → ClaudeClient
      2. LLM_PROVIDER == "claude" AND key missing → log warning, return OllamaClient
      3. LLM_PROVIDER == "ollama" (or any other value) → OllamaClient

    Returns:
        LLMClient instance ready for use.
    """
    from app.core.config import settings

    if settings.LLM_PROVIDER == "claude":
        if not settings.ANTHROPIC_API_KEY:
            logger.warning(
                "[LLM_FACTORY] LLM_PROVIDER=claude but ANTHROPIC_API_KEY is not set. "
                "Falling back to OllamaClient. Set ANTHROPIC_API_KEY to use Claude."
            )
            from app.ai.ollama_client import OllamaClient
            return OllamaClient()
        from app.ai.claude_client import ClaudeClient
        return ClaudeClient()

    from app.ai.ollama_client import OllamaClient
    return OllamaClient()
