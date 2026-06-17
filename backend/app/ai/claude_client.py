"""
app/ai/claude_client.py — Anthropic Claude API client with prompt caching.

Implements the LLMClient protocol so it's a drop-in replacement for OllamaClient.

Prompt caching (REQ-1.3):
  Attaches cache_control: {"type": "ephemeral"} to the system prompt block.
  This caches up to 1024 tokens of the system prompt across API calls,
  reducing cost and latency for repeated system instructions.
  Cache-hit token counts are logged at DEBUG level.

Configuration (from settings):
  ANTHROPIC_API_KEY  — required (validated by factory before construction)
  CLAUDE_MODEL       — model name (default: claude-haiku-4-5)
  OLLAMA_TEMPERATURE — reused as default temperature
  OLLAMA_MAX_TOKENS  — reused as default max_tokens
"""
from __future__ import annotations

import logging
import time
from typing import AsyncIterator

from app.ai.llm_factory import LLMResponse
from app.core.config import settings
from app.core.exceptions import UnprocessableError

logger = logging.getLogger("ai_coach.claude_client")


class ClaudeClient:
    """
    Async Anthropic Claude client with prompt caching support.

    Satisfies the LLMClient protocol defined in llm_factory.py.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (default from settings.ANTHROPIC_API_KEY)
            model: Claude model name (default from settings.CLAUDE_MODEL)
        """
        self._api_key = api_key or settings.ANTHROPIC_API_KEY
        self._model = model or settings.CLAUDE_MODEL

        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is required for ClaudeClient. "
                "Install it with: pip install anthropic"
            ) from exc

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a completion using the Claude API.

        The system prompt is sent with cache_control to enable prompt caching.
        Cache hit/miss token counts are logged at DEBUG level.

        Args:
            prompt: user prompt text
            system: optional system message (cached if provided)
            temperature: sampling temperature (default from settings)
            max_tokens: max completion tokens (default from settings)

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            UnprocessableError: when API call or response parsing fails
        """
        temperature = temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.OLLAMA_MAX_TOKENS

        try:
            import anthropic
            start_time = time.time()

            # Build messages with optional cached system block
            messages = self._build_messages(prompt, system)

            kwargs: dict = dict(
                model=self._model,
                max_tokens=max_tokens,
                messages=messages,
            )
            # Temperature 0 maps to deterministic in Claude; pass only when non-default
            if temperature is not None:
                kwargs["temperature"] = temperature

            response = await self._client.messages.create(**kwargs)

            response_time_ms = int((time.time() - start_time) * 1000)

            # Extract content
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            if not content:
                raise UnprocessableError("Claude returned empty response")

            # Token counts
            usage = response.usage
            prompt_tokens = getattr(usage, "input_tokens", 0)
            completion_tokens = getattr(usage, "output_tokens", 0)
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

            logger.debug(
                "[CLAUDE] tokens: prompt=%d completion=%d "
                "cache_read=%d cache_write=%d time=%dms",
                prompt_tokens, completion_tokens, cache_read, cache_write, response_time_ms,
            )

            return LLMResponse(
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                response_time_ms=response_time_ms,
                model_used=self._model,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
            )

        except UnprocessableError:
            raise
        except Exception as exc:
            logger.error("[CLAUDE] generation failed: %s: %s", type(exc).__name__, exc)
            raise UnprocessableError(
                f"Claude API error: {type(exc).__name__}: {exc}"
            ) from exc

    async def stream_generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens from the Claude API.

        Args:
            prompt: user prompt text
            system: optional system message
            temperature: sampling temperature
            max_tokens: max completion tokens

        Yields:
            text chunks as they are streamed

        Raises:
            UnprocessableError: when streaming fails
        """
        temperature = temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.OLLAMA_MAX_TOKENS

        try:
            messages = self._build_messages(prompt, system)
            kwargs: dict = dict(
                model=self._model,
                max_tokens=max_tokens,
                messages=messages,
            )
            if temperature is not None:
                kwargs["temperature"] = temperature

            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield text

        except Exception as exc:
            logger.error("[CLAUDE] stream failed: %s: %s", type(exc).__name__, exc)
            raise UnprocessableError(
                f"Claude streaming error: {type(exc).__name__}: {exc}"
            ) from exc

    def _build_messages(self, prompt: str, system: str | None) -> list[dict]:
        """
        Build the messages list for the Claude API call.

        When a system prompt is provided, it is placed as the first content
        block in the user message with cache_control to enable prompt caching.
        This allows the static system context to be cached between requests.

        Args:
            prompt: the user's dynamic prompt
            system: optional static system instructions to cache

        Returns:
            list of message dicts for the Claude messages.create() call
        """
        if system:
            # Combine system + user content in a single user message.
            # The system block gets cache_control so Anthropic caches it.
            return [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ]
        return [{"role": "user", "content": prompt}]
