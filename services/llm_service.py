from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from services.config_service import Settings


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


class LLMService:
    _DEFAULT_MODEL_PRICING_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
        "gpt-4.1-mini": (0.40, 1.60),
    }

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self._model = settings.llm_model
        self._input_cost_per_1m_tokens = settings.llm_input_cost_per_1m_tokens
        self._output_cost_per_1m_tokens = settings.llm_output_cost_per_1m_tokens

    def generate_json(self, messages: list[dict[str, str]]) -> LLMJsonResponse:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")
        return LLMJsonResponse(
            payload=json.loads(self._extract_json(content)),
            usage=self._build_usage(response),
            model=response.model or self._model,
        )

    def generate_text(self, messages: list[dict[str, str]]) -> str:
        """Generate plain text response (not JSON)."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")
        return content.strip()

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
