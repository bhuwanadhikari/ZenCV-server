import json
import re
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
from services.llm_service import LLMService, LLMUsage
from services.prompt_service import build_cover_letter_messages, build_cv_messages
from services.story_service import load_story_json

CV_VARIANTS_PATH = Path("data/cv-data/cv_variants.json")
CV_VARIANTS_EXAMPLE_PATH = Path("data/cv-data/cv_variants.example.json")
GENERATED_CVS_PATH = Path("data/generated")
GENERATED_CV_JSON_FILENAME = "generated_cv.json"
GENERATED_CV_MARKDOWN_FILENAME = "generated_cv.md"
CV_DATA_ADAPTER = TypeAdapter(CvData)
CV_DATA_LIST_ADAPTER = TypeAdapter(list[CvData])


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    llm_service = LLMService(settings)
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


def sanitize_page_title(page_title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", page_title).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Untitled Page"


def build_generated_cv_directory(page_title: str) -> Path:
    GENERATED_CVS_PATH.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_page_title(page_title)

    counter = 1
    while True:
        folder_name = base_name if counter == 1 else f"{base_name} ({counter})"
        directory = GENERATED_CVS_PATH / folder_name
        try:
            directory.mkdir()
            return directory
        except FileExistsError:
            counter += 1


def yaml_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def to_yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = "  " * indent

    if isinstance(value, dict):
        if not value:
            return [f"{prefix}{{}}"]

        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                if not item:
                    empty_value = "{}" if isinstance(item, dict) else "[]"
                    lines.append(f"{prefix}{key}: {empty_value}")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.extend(to_yaml_lines(item, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]

        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                if not item:
                    empty_value = "{}" if isinstance(item, dict) else "[]"
                    lines.append(f"{prefix}- {empty_value}")
                else:
                    lines.append(f"{prefix}-")
                    lines.extend(to_yaml_lines(item, indent + 1))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines

    return [f"{prefix}{yaml_scalar(value)}"]


def to_yaml_string(value: Any) -> str:
    return "\n".join(to_yaml_lines(value))


def save_generated_cv_artifacts(
    *,
    page_title: str,
    job_url: str,
    generated_cv: CvData,
    llm_model: str,
    llm_usage: Optional[LLMUsage],
) -> Path:
    output_directory = build_generated_cv_directory(page_title)
    cv_payload = generated_cv.model_dump(mode="json")
    yaml_content = to_yaml_string(cv_payload)

    json_path = output_directory / GENERATED_CV_JSON_FILENAME
    markdown_path = output_directory / GENERATED_CV_MARKDOWN_FILENAME

    json_path.write_text(
        json.dumps(cv_payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    request_metrics_lines = [
        "## Request Metrics",
        "",
        f"- Model: {llm_model}",
    ]
    if llm_usage is None:
        request_metrics_lines.append("- Token Usage: Unavailable")
        request_metrics_lines.append("- Estimated Cost (USD): Unavailable")
    else:
        request_metrics_lines.extend(
            [
                f"- Prompt Tokens: {llm_usage.prompt_tokens}",
                f"- Completion Tokens: {llm_usage.completion_tokens}",
                f"- Total Tokens: {llm_usage.total_tokens}",
                "- Estimated Cost (USD): "
                + (
                    f"${llm_usage.estimated_cost_usd:.6f}"
                    if llm_usage.estimated_cost_usd is not None
                    else "Unavailable"
                ),
            ]
        )

    markdown_path.write_text(
        "\n".join(
            [
                "# Generated CV",
                "",
                f"- Page Title: {page_title}",
                f"- Job URL: {job_url}",
                "",
                *request_metrics_lines,
                "",
                "## CV YAML",
                "",
                "```yaml",
                yaml_content,
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return output_directory


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
        llm_response = get_llm_service().generate_json(messages)
        generated_cv = CV_DATA_ADAPTER.validate_python(llm_response.payload)
        validated_cv = validate_generated_cv(generated_cv)
        print(
            "Generated CV JSON:\n"
            + json.dumps(
                validated_cv.model_dump(mode="json"), indent=2, ensure_ascii=True
            )
        )
        try:
            output_directory = save_generated_cv_artifacts(
                page_title=request.page_title,
                job_url=request.job_url,
                generated_cv=validated_cv,
                llm_model=llm_response.model,
                llm_usage=llm_response.usage,
            )
            print(f"Saved generated CV artifacts to: {output_directory}")
        except OSError as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to save generated CV artifacts: {exc}"
            ) from exc
        return validated_cv
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail=f"Invalid generated CV: {exc}"
        ) from exc
    except HTTPException:
        raise
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
        llm_response = get_llm_service().generate_json(messages)
        cover_letter = llm_response.payload["cover_letter"]
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
