import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pydantic import TypeAdapter

from schemas.generation_schema import (
    CvData,
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GenerateCvRequest,
)
from services.config_service import get_settings
from services.llm_service import LLMService
from services.prompt_service import build_cover_letter_messages, build_cv_messages
from services.story_service import load_story_json

CV_VARIANTS_PATH = Path("data/cv-data/cv_variants.json")
CV_VARIANTS_EXAMPLE_PATH = Path("data/cv-data/cv_variants.example.json")
CV_DATA_ADAPTER = TypeAdapter(CvData)
CV_DATA_LIST_ADAPTER = TypeAdapter(list[CvData])


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    print('FROM THE LLM SERVICE RUNNEE---------------')
    llm_service = LLMService(settings)
    api_key = settings.llm_api_key
    masked_api_key = (
        "*" * max(len(api_key) - 4, 0) + api_key[-4:]
        if len(api_key) > 4
        else "*" * len(api_key)
    )
    print(f"Loaded LLM API key: {masked_api_key}")
    return llm_service


def resolve_story_json(override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if override is not None:
        return override
    settings = get_settings()
    return load_story_json(settings.my_story_json_path)


def load_cv_variants(path: Path) -> list[CvData]:
    cv_variants_data = json.loads(path.read_text(encoding="utf-8"))
    return CV_DATA_LIST_ADAPTER.validate_python(cv_variants_data)


@lru_cache
def get_cv_variants() -> list[CvData]:
    selected_path = CV_VARIANTS_PATH
    if not selected_path.exists():
        selected_path = CV_VARIANTS_EXAMPLE_PATH

    cv_variants = load_cv_variants(selected_path)
    if not cv_variants and selected_path != CV_VARIANTS_EXAMPLE_PATH:
        cv_variants = load_cv_variants(CV_VARIANTS_EXAMPLE_PATH)

    if not cv_variants:
        raise ValueError("No CV variants found in the configured data files.")

    return cv_variants


def validate_generated_cv(cv_data: CvData) -> CvData:
    return cv_data


def generate_cv_content(request: GenerateCvRequest) -> CvData:
    try:
        cv_variants = get_cv_variants()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500, detail=f"CV variants file not found: {exc}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to load CV variants: {exc}"
        ) from exc

    try:
        messages = build_cv_messages(
            job_description=request.job_description,
            cv_variants=[variant.model_dump(mode="json") for variant in cv_variants],
        )
        print('HERE IS THE THING-------------------------')
        llm_output = get_llm_service().generate_json(messages)
        generated_cv = CV_DATA_ADAPTER.validate_python(llm_output)
        validated_cv = validate_generated_cv(generated_cv)
        print(
            "Generated CV JSON:\n"
            + json.dumps(validated_cv.model_dump(mode="json"), indent=2, ensure_ascii=True)
        )
        return validated_cv
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail=f"Invalid generated CV: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to generate CV: {exc}"
        ) from exc


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
            raise ValueError(
                "LLM response did not include a valid cover_letter string."
            )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500, detail=f"Story JSON file not found: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to generate cover letter: {exc}"
        ) from exc

    return GenerateCoverLetterResponse(cover_letter=cover_letter.strip())
