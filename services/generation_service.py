import json
import hashlib
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

CV_VARIANTS_PATH = Path("data/cv-data/cv_variants.json")
CV_VARIANTS_EXAMPLE_PATH = Path("data/cv-data/cv_variants.example.json")
GENERATED_CVS_PATH = Path("data/generated")
GENERATED_CV_JSON_FILENAME = "generated_cv.json"
GENERATED_CV_MARKDOWN_FILENAME = "generated_cv.md"
CV_YAML_SECTION_HEADING = "## CV YAML"
COVER_LETTER_SECTION_HEADING = "## Cover Letter"
CV_DATA_ADAPTER = TypeAdapter(CvData)
CV_DATA_LIST_ADAPTER = TypeAdapter(list[CvData])


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    llm_service = LLMService(settings)
    return llm_service


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


def hash_job_url(job_url: str) -> str:
    normalized_job_url = job_url.strip()
    return hashlib.sha256(normalized_job_url.encode("utf-8")).hexdigest()[:16]


def build_generated_cv_directory(job_url: str) -> Path:
    GENERATED_CVS_PATH.mkdir(parents=True, exist_ok=True)
    return GENERATED_CVS_PATH / hash_job_url(job_url)


# TODO: later use the cv json that's previously generated to make better cover letter
def find_generated_cv_directory(job_url: str) -> Optional[Path]:
    GENERATED_CVS_PATH.mkdir(parents=True, exist_ok=True)
    hashed_directory = build_generated_cv_directory(job_url)
    if hashed_directory.is_dir():
        return hashed_directory

    folder_suffix = f"__{hash_job_url(job_url)}"
    matches = sorted(
        path for path in GENERATED_CVS_PATH.glob(f"*{folder_suffix}") if path.is_dir()
    )
    if matches:
        legacy_directory = matches[0]
        try:
            legacy_directory.rename(hashed_directory)
            return hashed_directory
        except OSError:
            return legacy_directory
    return None


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


def escape_markdown_link_text(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")


def build_markdown_header(page_title: str, job_url: str) -> list[str]:
    escaped_title = escape_markdown_link_text(page_title)
    return [
        "# Generated Application",
        "",
        f"- Page: [{escaped_title}]({job_url})",
    ]


def build_request_metrics_lines(
    *,
    artifact_label: str,
    llm_model: str,
    llm_usage: Optional[LLMUsage],
) -> list[str]:
    lines = [
        f"## {artifact_label} Request Metrics",
        "",
        f"- Model: {llm_model}",
    ]
    if llm_usage is None:
        lines.append("- Token Usage: Unavailable")
        lines.append("- Estimated Cost (USD): Unavailable")
        return lines

    lines.extend(
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
    return lines


def read_markdown_content(markdown_path: Path) -> str:
    if not markdown_path.exists():
        return ""
    return markdown_path.read_text(encoding="utf-8")


def append_markdown_sections(markdown_path: Path, sections: list[str]) -> None:
    existing_content = read_markdown_content(markdown_path).rstrip()
    appended_content = "\n".join(sections).strip()

    if existing_content:
        markdown_path.write_text(
            existing_content + "\n\n" + appended_content + "\n",
            encoding="utf-8",
        )
        return

    markdown_path.write_text(appended_content + "\n", encoding="utf-8")


def markdown_contains_cv_yaml(markdown_content: str) -> bool:
    return CV_YAML_SECTION_HEADING in markdown_content


def markdown_contains_cover_letter(markdown_content: str) -> bool:
    return COVER_LETTER_SECTION_HEADING in markdown_content


def reject_if_cv_already_generated(job_url: str) -> Optional[Path]:
    output_directory = find_generated_cv_directory(job_url)
    if output_directory is None:
        return None

    json_path = output_directory / GENERATED_CV_JSON_FILENAME
    markdown_path = output_directory / GENERATED_CV_MARKDOWN_FILENAME
    markdown_content = read_markdown_content(markdown_path)
    if json_path.exists() or markdown_contains_cv_yaml(markdown_content):
        raise HTTPException(
            status_code=409,
            detail="A CV has already been generated for this job URL.",
        )
    return output_directory


def reject_if_cover_letter_already_generated(job_url: str) -> Optional[Path]:
    output_directory = find_generated_cv_directory(job_url)
    if output_directory is None:
        return None

    markdown_path = output_directory / GENERATED_CV_MARKDOWN_FILENAME
    markdown_content = read_markdown_content(markdown_path)
    if markdown_contains_cover_letter(markdown_content):
        raise HTTPException(
            status_code=409,
            detail="A cover letter has already been generated for this job URL.",
        )
    return output_directory


def save_generated_cv_artifacts(
    *,
    page_title: str,
    job_url: str,
    generated_cv: CvData,
    llm_model: str,
    llm_usage: Optional[LLMUsage],
) -> Path:
    output_directory = find_generated_cv_directory(job_url) or build_generated_cv_directory(
        job_url
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    cv_payload = generated_cv.model_dump(mode="json")
    yaml_content = to_yaml_string(cv_payload)

    json_path = output_directory / GENERATED_CV_JSON_FILENAME
    markdown_path = output_directory / GENERATED_CV_MARKDOWN_FILENAME

    json_path.write_text(
        json.dumps(cv_payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    markdown_sections = []
    if not markdown_path.exists():
        markdown_sections.extend(build_markdown_header(page_title, job_url))

    markdown_sections.extend(
        [
            "",
            *build_request_metrics_lines(
                artifact_label="CV",
                llm_model=llm_model,
                llm_usage=llm_usage,
            ),
            "",
            CV_YAML_SECTION_HEADING,
            "",
            "```yaml",
            yaml_content,
            "```",
        ]
    )
    append_markdown_sections(markdown_path, markdown_sections)

    return output_directory


def save_generated_cover_letter_artifacts(
    *,
    page_title: str,
    job_url: str,
    cover_letter: str,
    llm_model: str,
    llm_usage: Optional[LLMUsage],
) -> Path:
    output_directory = find_generated_cv_directory(job_url) or build_generated_cv_directory(
        job_url
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    markdown_path = output_directory / GENERATED_CV_MARKDOWN_FILENAME

    markdown_sections = []
    if not markdown_path.exists():
        markdown_sections.extend(build_markdown_header(page_title, job_url))

    markdown_sections.extend(
        [
            "",
            *build_request_metrics_lines(
                artifact_label="Cover Letter",
                llm_model=llm_model,
                llm_usage=llm_usage,
            ),
            "",
            COVER_LETTER_SECTION_HEADING,
            "",
            cover_letter.strip(),
        ]
    )
    append_markdown_sections(markdown_path, markdown_sections)

    return output_directory


def generate_cv_content(request: GenerateCvRequest) -> CvData:
    reject_if_cv_already_generated(request.job_url)

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
    reject_if_cover_letter_already_generated(request.job_url)

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
        messages = build_cover_letter_messages(
            page_title=request.page_title,
            job_url=request.job_url,
            job_description=request.job_description,
            cv_variants=[variant.model_dump(mode="json") for variant in cv_variants],
            generated_cv=request.generated_cv,
            story_json=request.story_json_override,
        )
        llm_response = get_llm_service().generate_json(messages)
        cover_letter = llm_response.payload["cover_letter"]
        if not isinstance(cover_letter, str) or not cover_letter.strip():
            raise ValueError(
                "LLM response did not include a valid cover_letter string."
            )
        try:
            output_directory = save_generated_cover_letter_artifacts(
                page_title=request.page_title,
                job_url=request.job_url,
                cover_letter=cover_letter,
                llm_model=llm_response.model,
                llm_usage=llm_response.usage,
            )
            print(f"Saved generated cover letter artifacts to: {output_directory}")
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save generated cover letter artifacts: {exc}",
            ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail=f"Invalid generated cover letter: {exc}"
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to generate cover letter: {exc}"
        ) from exc

    return GenerateCoverLetterResponse(cover_letter=cover_letter.strip())
