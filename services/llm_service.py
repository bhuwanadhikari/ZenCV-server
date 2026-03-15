from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from services.config_service import Settings


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self._model = settings.llm_model

    def generate_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")
        return json.loads(self._extract_json(content))

    @staticmethod
    def _extract_json(content: str) -> str:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return cleaned
