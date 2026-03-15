from functools import lru_cache
from typing import Any, Dict, Optional

from fastapi import HTTPException

from schemas.generation_schema import (
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GeneratedCv,
    GenerateCvRequest,
    GenerateCvResponse,
)
from services.config_service import get_settings
from services.llm_service import LLMService
from services.prompt_service import build_cover_letter_messages, build_cv_messages
from services.story_service import load_story_json


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService(get_settings())


def resolve_story_json(override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if override is not None:
        return override
    settings = get_settings()
    return load_story_json(settings.my_story_json_path)


def generate_cv_content(request: GenerateCvRequest) -> GenerateCvResponse:
    try:
        story_json = resolve_story_json(request.story_json_override)
        messages = build_cv_messages(
            job_description=request.job_description,
            story_json=story_json,
        )
        llm_output = get_llm_service().generate_json(messages)
        generated_cv = GeneratedCv.model_validate(llm_output)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Story JSON file not found: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to generate CV: {exc}") from exc

    return GenerateCvResponse(cv=generated_cv)


def generate_cover_letter_content(
    request: GenerateCoverLetterRequest,
) -> GenerateCoverLetterResponse:
    try:
        story_json = resolve_story_json(request.story_json_override)
        messages = build_cover_letter_messages(
            job_description=request.job_description,
            generated_cv=request.generated_cv,
            story_json=story_json,
        )
        llm_output = get_llm_service().generate_json(messages)
        cover_letter = llm_output["cover_letter"]
        if not isinstance(cover_letter, str) or not cover_letter.strip():
            raise ValueError("LLM response did not include a valid cover_letter string.")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Story JSON file not found: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to generate cover letter: {exc}") from exc

    return GenerateCoverLetterResponse(cover_letter=cover_letter.strip())
