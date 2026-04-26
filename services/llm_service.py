from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import OpenAI

from services.config_service import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None


@dataclass(frozen=True)
class LLMJsonResponse:
    payload: dict[str, Any]
    usage: LLMUsage | None
    model: str


@dataclass(frozen=True)
class LLMTextResponse:
    content: str
    usage: LLMUsage | None
    model: str


class LLMService:
    _DEFAULT_MODEL_PRICING_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
        "gpt-4.1-mini": (0.40, 1.60),
    }
    _MAX_RETRIES = 3
    _INITIAL_RETRY_DELAY = 1  # seconds
    _RETRY_BACKOFF_FACTOR = 2

    def __init__(self, settings: Settings) -> None:
        # Create a custom HTTP client with better SSL/TLS handling
        http_client = httpx.Client(
            verify=True,  # Keep SSL verification enabled
            timeout=httpx.Timeout(
                timeout=settings.llm_timeout_seconds,
                connect=10,
                read=settings.llm_timeout_seconds,
                write=10,
                pool=10,
            ),
        )
        
        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            http_client=http_client,
        )
        self._model = settings.llm_model
        self._input_cost_per_1m_tokens = settings.llm_input_cost_per_1m_tokens
        self._output_cost_per_1m_tokens = settings.llm_output_cost_per_1m_tokens

    @property
    def model_name(self) -> str:
        return self._model

    def generate_json(self, messages: list[dict[str, str]]) -> LLMJsonResponse:
        response = self._retry_with_backoff(
            lambda: self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")
        return LLMJsonResponse(
            payload=json.loads(self._extract_json(content)),
            usage=self._build_usage(response),
            model=response.model or self._model,
        )

    def generate_text(self, messages: list[dict[str, str]]) -> LLMTextResponse:
        """Generate plain text response with request metadata."""
        response = self._retry_with_backoff(
            lambda: self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
            )
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")
        return LLMTextResponse(
            content=content.strip(),
            usage=self._build_usage(response),
            model=response.model or self._model,
        )

    @staticmethod
    def _extract_json(content: str) -> str:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return cleaned

    def _build_usage(self, response: Any) -> LLMUsage | None:
        usage = response.usage
        if usage is None:
            return None

        prompt_tokens = int(usage.prompt_tokens or 0)
        completion_tokens = int(usage.completion_tokens or 0)
        total_tokens = int(usage.total_tokens or (prompt_tokens + completion_tokens))
        estimated_cost_usd = self._estimate_cost_usd(
            model_name=response.model or self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )

    def _estimate_cost_usd(
        self,
        *,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float | None:
        token_rates = self._resolve_token_rates(model_name)
        if token_rates is None:
            return None

        input_cost_per_1m_tokens, output_cost_per_1m_tokens = token_rates
        return (
            (prompt_tokens / 1_000_000) * input_cost_per_1m_tokens
            + (completion_tokens / 1_000_000) * output_cost_per_1m_tokens
        )

    def _resolve_token_rates(self, model_name: str) -> tuple[float, float] | None:
        if (
            self._input_cost_per_1m_tokens is not None
            and self._output_cost_per_1m_tokens is not None
        ):
            return (
                self._input_cost_per_1m_tokens,
                self._output_cost_per_1m_tokens,
            )

        for candidate in (model_name, self._model):
            exact_match = self._DEFAULT_MODEL_PRICING_PER_1M_TOKENS.get(candidate)
            if exact_match is not None:
                return exact_match

        for base_model, token_rates in self._DEFAULT_MODEL_PRICING_PER_1M_TOKENS.items():
            if model_name.startswith(f"{base_model}-") or self._model.startswith(
                f"{base_model}-"
            ):
                return token_rates

        return None

    def _retry_with_backoff(self, func):
        """
        Retry a function call with exponential backoff for transient errors.
        This helps handle SSL and network-related issues.
        """
        import ssl
        
        last_exception = None
        
        for attempt in range(self._MAX_RETRIES):
            try:
                return func()
            except (
                ssl.SSLError,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.TimeoutException,
                ConnectionError,
                ConnectionResetError,
                ConnectionAbortedError,
            ) as e:
                last_exception = e
                
                # Check if this is the last attempt
                if attempt >= self._MAX_RETRIES - 1:
                    logger.error(
                        f"LLM request failed after {self._MAX_RETRIES} attempts. "
                        f"Last error: {type(e).__name__}: {str(e)}"
                    )
                    raise
                
                # Calculate delay with exponential backoff
                delay = self._INITIAL_RETRY_DELAY * (self._RETRY_BACKOFF_FACTOR ** attempt)
                logger.warning(
                    f"LLM request failed (attempt {attempt + 1}/{self._MAX_RETRIES}): "
                    f"{type(e).__name__}: {str(e)}. Retrying in {delay}s..."
                )
                time.sleep(delay)
        
        # This should not be reached, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in retry mechanism")
