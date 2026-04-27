import json
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from lxml import html as lxml_html
from pydantic import TypeAdapter

from schemas.generation_schema import (
    CvData,
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GenerateCvRequest,
    ProcessCvHtmlRequest,
    ProcessedCvHtmlResponse,
)
from services.config_service import get_settings
from services.llm_service import LLMService, LLMUsage
from services.prompt_service import build_cover_letter_messages, build_cv_messages

CV_VARIANTS_PATH = Path("data/user-profile/cv_variants.json")
CV_VARIANTS_EXAMPLE_PATH = Path("data/user-profile/cv_variants.example.json")
GENERATED_CVS_PATH = Path("data/generated")
GENERATED_CV_JSON_FILENAME = "generated_cv.json"
GENERATION_SUMMARY_FILENAME = "generation_summary.md"
GENERATED_CL_FILENAME = "generated_cl.txt"
GENERATED_JD_FILENAME = "generated_jd.txt"
CV_DATA_ADAPTER = TypeAdapter(CvData)
CV_DATA_LIST_ADAPTER = TypeAdapter(list[CvData])
USE_LLM_TO_EXTRACT_JD = True  # Set to True to use LLM for job description extraction, setting to false will not work
IGNORED_BODY_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "meta",
    "link",
    "base",
    "img",
    "picture",
    "video",
    "audio",
    "source",
    "track",
    "canvas",
    "svg",
    "iframe",
    "embed",
    "object",
    "form",
    "input",
    "textarea",
    "button",
    "select",
    "option",
    "label",
    "fieldset",
    "legend",
    "nav",
    "aside",
    "footer",
    "header",
    "hr",
    "wbr",
    "a",
)
INLINE_FLATTEN_TAGS = ("b", "font", "br", "i", "span", "strong", "em")
IGNORED_INTERACTIVE_ROLES = ("button", "link")


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


def build_request_metrics_lines(
    *,
    artifact_label: str,
    llm_model: str,
    llm_usage: Optional[LLMUsage],
    heading_prefix: str = "##",
) -> list[str]:
    lines = [
        f"{heading_prefix} {artifact_label} Request Metrics",
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


def append_generation_summary(
    *,
    output_directory: Path,
    artifact_label: str,
    content: str,
    content_language: str,
    llm_model: str,
    llm_usage: Optional[LLMUsage],
) -> None:
    summary_path = output_directory / GENERATION_SUMMARY_FILENAME
    summary_sections: list[str] = []

    if not summary_path.exists():
        summary_sections.extend(["# Generation Summary", ""])

    summary_sections.extend(
        [
            f"## {artifact_label}",
            "",
            *build_request_metrics_lines(
                artifact_label=artifact_label,
                llm_model=llm_model,
                llm_usage=llm_usage,
                heading_prefix="###",
            ),
            "",
            f"```{content_language}",
            content.strip(),
            "```",
        ]
    )
    append_markdown_sections(summary_path, summary_sections)


def load_cached_generated_cv(job_url: str) -> Optional[CvData]:
    output_directory = find_generated_cv_directory(job_url)
    if output_directory is None:
        return None

    json_path = output_directory / GENERATED_CV_JSON_FILENAME
    if not json_path.exists():
        return None

    try:
        cached_payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to read cached CV from {json_path}: {exc}")
        return None

    try:
        return CV_DATA_ADAPTER.validate_python(cached_payload)
    except ValueError as exc:
        print(f"Cached CV at {json_path} is invalid: {exc}")
        return None


def load_cached_cover_letter(job_url: str) -> Optional[str]:
    output_directory = find_generated_cv_directory(job_url)
    if output_directory is None:
        return None

    cover_letter_path = output_directory / GENERATED_CL_FILENAME
    if not cover_letter_path.exists():
        return None

    try:
        cover_letter = cover_letter_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"Failed to read cached cover letter from {cover_letter_path}: {exc}")
        return None

    return cover_letter or None


def load_cached_job_description(job_url: str) -> Optional[str]:
    """Load cached job description from file if it exists."""
    output_directory = find_generated_cv_directory(job_url)
    if output_directory is None:
        return None

    jd_path = output_directory / GENERATED_JD_FILENAME
    if not jd_path.exists():
        return None

    try:
        job_description = jd_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"Failed to read cached job description from {jd_path}: {exc}")
        return None

    return job_description or None


def save_job_description(job_url: str, job_description: str) -> Path:
    """Save extracted job description to file."""
    output_directory = find_generated_cv_directory(job_url) or build_generated_cv_directory(
        job_url
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    jd_path = output_directory / GENERATED_JD_FILENAME
    jd_path.write_text(job_description.strip() + "\n", encoding="utf-8")

    return output_directory


def save_generated_cv_artifacts(
    *,
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

    json_path.write_text(
        json.dumps(cv_payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    append_generation_summary(
        output_directory=output_directory,
        artifact_label="CV",
        content=yaml_content,
        content_language="yaml",
        llm_model=llm_model,
        llm_usage=llm_usage,
    )

    return output_directory


def save_generated_cover_letter_artifacts(
    *,
    job_url: str,
    cover_letter: str,
    llm_model: str,
    llm_usage: Optional[LLMUsage],
) -> Path:
    output_directory = find_generated_cv_directory(job_url) or build_generated_cv_directory(
        job_url
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    cover_letter_path = output_directory / GENERATED_CL_FILENAME
    normalized_cover_letter = cover_letter.strip()

    cover_letter_path.write_text(normalized_cover_letter + "\n", encoding="utf-8")
    append_generation_summary(
        output_directory=output_directory,
        artifact_label="Cover Letter",
        content=normalized_cover_letter,
        content_language="text",
        llm_model=llm_model,
        llm_usage=llm_usage,
    )

    return output_directory


def extract_text_from_body_element(body_element: Any) -> str:
    """
    Extract text from body element after step 5 (after flattening inline tags).
    Returns text separated by line breaks.
    """
    def normalize_text(value: str) -> str:
        return " ".join(value.split())

    def has_child_elements(element: Any) -> bool:
        for child in element:
            if isinstance(getattr(child, "tag", None), str):
                return True
        return False

    text_lines: list[str] = []
    for element in body_element.iter():
        if not isinstance(getattr(element, "tag", None), str):
            continue
        if has_child_elements(element):
            continue

        normalized_element_text = normalize_text(element.text_content() or "")
        if normalized_element_text:
            text_lines.append(normalized_element_text)

    if not text_lines:
        return normalize_text(body_element.text_content() or "")

    return "\n".join(text_lines)


def extract_job_description_with_llm(text_content: str) -> tuple[str, str, Optional[LLMUsage]]:
    """
    Use LLM to extract job description details from plain text.
    Sends the text with an advanced prompt to extract:
    - Job description section
    - Company details
    - Position
    - Date
    - Address
    - Full/Part-time status
    - All other relevant job details
    """
    from services.prompt_service import build_job_description_extraction_prompt

    llm_service = get_llm_service()
    messages = build_job_description_extraction_prompt(text_content)

    try:
        response = llm_service.generate_text(messages)
        return response.content, response.model, response.usage
    except Exception as e:
        print(f"LLM extraction failed: {e}. Falling back to original text.")
        return text_content, llm_service.model_name, None


def extract_body_html(raw_html: str, job_url: Optional[str] = None) -> str:
    print("Extracting body HTML content...", raw_html)
    # Check if job description is already cached
    if job_url:
        cached_jd = load_cached_job_description(job_url)
        if cached_jd:
            return cached_jd

    # # Step 1: Parse the incoming HTML. If parsing fails, return the original
    # # payload unchanged so the frontend still gets something usable back.
    # try:
    #     parsed_html = lxml_html.fromstring(raw_html)
    # except (lxml_html.ParserError, ValueError):
    #     return raw_html

    # Step 2: Find the first body element. If there is no body tag, fall back
    # to the original HTML instead of trying to invent a wrapper.
    # body_elements = parsed_html.xpath("//body")
    # if not body_elements:
    #     return raw_html

    # body_element = body_elements[0]

    # def normalize_text(value: str) -> str:
    #     return " ".join(value.split())

    # def remove_element_preserving_tail(element: Any) -> None:
    #     parent = element.getparent()
    #     if parent is None:
    #         return

    #     # When we remove an ignored subtree, keep any trailing text that came
    #     # after the element so nearby content is not accidentally dropped.
    #     tail_text = element.tail or ""
    #     previous_sibling = element.getprevious()
    #     if tail_text:
    #         if previous_sibling is not None:
    #             previous_sibling.tail = (previous_sibling.tail or "") + tail_text
    #         else:
    #             parent.text = (parent.text or "") + tail_text

    #     parent.remove(element)

    # def has_child_elements(element: Any) -> bool:
    #     for child in element:
    #         if isinstance(getattr(child, "tag", None), str):
    #             return True
    #     return False

    # def find_lowest_common_ancestor(elements: list[Any]) -> Any:
    #     if not elements:
    #         return None

    #     first_ancestor_chain: list[Any] = []
    #     current = elements[0]
    #     while current is not None and isinstance(getattr(current, "tag", None), str):
    #         first_ancestor_chain.append(current)
    #         current = current.getparent()

    #     other_ancestor_ids: list[set[int]] = []
    #     for element in elements[1:]:
    #         ancestor_ids: set[int] = set()
    #         current = element
    #         while current is not None and isinstance(getattr(current, "tag", None), str):
    #             ancestor_ids.add(id(current))
    #             current = current.getparent()
    #         other_ancestor_ids.append(ancestor_ids)

    #     for ancestor in first_ancestor_chain:
    #         if all(id(ancestor) in ancestor_ids for ancestor_ids in other_ancestor_ids):
    #             return ancestor

    #     return elements[0]

    # def find_grandparent(element: Any) -> Any:
    #     current = element
    #     # TODO: check the depth here
    #     for _ in range(4):
    #         parent = current.getparent()
    #         if parent is None or not isinstance(getattr(parent, "tag", None), str):
    #             return current
    #         current = parent
    #     return current

    # Step 3: Remove all non-content tags one tag-name at a time. This is more
    # explicit than a single combined XPath and easier to debug or tweak later.
    # Each removal drops the whole subtree for that ignored tag, including all
    # of its children.
    # for tag_name in IGNORED_BODY_TAGS:
    #     matching_elements = list(body_element.xpath(f".//{tag_name}"))
    #     for removable_element in matching_elements:
    #         remove_element_preserving_tail(removable_element)

    # Step 4: Remove interactive wrappers when they contain child elements.
    # Keep plain text links or button-like containers, but drop wrappers such
    # as <a><p>...</p></a> or <div role="button"><span>...</span></div>.
    # for element in list(body_element.iter()):
    #     if not isinstance(getattr(element, "tag", None), str):
    #         continue

    #     tag_name = element.tag.lower()
    #     role_tokens = (element.get("role") or "").strip().lower().split()
    #     is_anchor_tag = tag_name == "a"
    #     has_interactive_role = any(
    #         role_token in IGNORED_INTERACTIVE_ROLES for role_token in role_tokens
    #     )
    #     if (is_anchor_tag or has_interactive_role) and has_child_elements(element):
    #         remove_element_preserving_tail(element)

    # Step 5: Flatten inline formatting tags one tag-name at a time so their
    # text stays in the document but the formatting tag itself disappears.
    # for tag_name in INLINE_FLATTEN_TAGS:
    #     matching_elements = list(body_element.xpath(f".//{tag_name}"))

    #     # Process from the deepest match back upward so nested inline tags are
    #     # unwrapped safely without invalidating later operations.
    #     for inline_element in reversed(matching_elements):
    #         if inline_element.tag == "br":
    #             parent = inline_element.getparent()
    #             if parent is None:
    #                 continue

    #             # Treat line breaks as plain spacing in the flattened output so
    #             # adjacent words do not collapse together.
    #             replacement_text = inline_element.tail or ""
    #             if replacement_text and not replacement_text.startswith(
    #                 (" ", "\n", "\t")
    #             ):
    #                 replacement_text = " " + replacement_text
    #             elif not replacement_text:
    #                 replacement_text = " "

    #             previous_sibling = inline_element.getprevious()
    #             if previous_sibling is not None:
    #                 previous_sibling.tail = (
    #                     previous_sibling.tail or ""
    #                 ) + replacement_text
    #             else:
    #                 parent.text = (parent.text or "") + replacement_text

    #             inline_element.tail = None
    #             remove_element_preserving_tail(inline_element)
    #             continue

    #         inline_element.drop_tag()

    # === BRANCHING POINT AFTER STEP 5 ===
    # Use LLM-based extraction if enabled and job_url is provided
    if USE_LLM_TO_EXTRACT_JD and job_url:
        text_content = raw_html
        (
            extracted_description,
            llm_model,
            llm_usage,
        ) = extract_job_description_with_llm(text_content)

        # Save the extracted job description
        output_directory = save_job_description(job_url, extracted_description)
        append_generation_summary(
            output_directory=output_directory,
            artifact_label="Job Description",
            content=extracted_description,
            content_language="text",
            llm_model=llm_model,
            llm_usage=llm_usage,
        )

        return extracted_description

    # Otherwise, continue with the original extraction method (Steps 6-9)

    # Step 6: Remove known page-specific junk containers that still slip
    # through the broader cleanup rules.
    # for translate_tooltip in list(body_element.xpath('.//*[@id="goog-gt-vt"]')):
    #     remove_element_preserving_tail(translate_tooltip)
    # for cv_match in list(
    #     body_element.xpath(
    #         './/div['
    #         'starts-with(normalize-space(@id), "cv-match")'
    #         ']'
    #     )
    # ):
    #     remove_element_preserving_tail(cv_match)

    # Step 7: From the cleaned HTML, pick the top 5 longest text-only elements.
    # A candidate element must not contain any child elements, so its content is
    # pure text after the cleanup and flattening passes above.
    # text_candidates: list[tuple[int, Any]] = []
    # for element in body_element.iter():
    #     if not isinstance(getattr(element, "tag", None), str):
    #         continue
    #     if has_child_elements(element):
    #         continue

    #     normalized_element_text = normalize_text(element.text_content() or "")
    #     if not normalized_element_text:
    #         continue

    #     text_candidates.append((len(normalized_element_text), element))

    # text_candidates.sort(key=lambda item: item[0], reverse=True)
    # selected_elements = [
    #     element for _, element in text_candidates[:5]
    # ]

    # Step 8: Find the lowest common parent of the selected top text elements,
    # then move up to its grandparent when possible. If we do not find
    # any candidates, fall back to the cleaned body element.
    # common_parent = find_lowest_common_ancestor(selected_elements)
    # if common_parent is None:
    #     target_element = body_element
    # else:
    #     target_element = find_grandparent(common_parent)

    # # Step 9: Convert the selected target element into readable plain text.
    # # Each leaf text element becomes its own line so the frontend gets clean
    # # line breaks instead of raw HTML.
    # text_lines: list[str] = []
    # for element in target_element.iter():
    #     if not isinstance(getattr(element, "tag", None), str):
    #         continue
    #     if has_child_elements(element):
    #         continue

    #     normalized_element_text = normalize_text(element.text_content() or "")
    #     if normalized_element_text:
    #         text_lines.append(normalized_element_text)

    # if not text_lines:
    #     return normalize_text(target_element.text_content() or "")

    # return "\n".join(text_lines)


def process_cv_html_content(
    request: ProcessCvHtmlRequest,
) -> ProcessedCvHtmlResponse:
    body_html = extract_body_html(request.raw_html, job_url=request.job_url)
    return ProcessedCvHtmlResponse(
        processed_text=body_html,
        processed_html=body_html,
    )


def generate_cv_content(request: GenerateCvRequest) -> CvData:
    cached_cv = load_cached_generated_cv(request.job_url)
    if cached_cv is not None:
        return cached_cv

    # Check for cached job description first
    cached_jd = load_cached_job_description(request.job_url)
    job_description = cached_jd if cached_jd else request.job_description

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
            job_description=job_description,
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
    cached_cover_letter = load_cached_cover_letter(request.job_url)
    if cached_cover_letter is not None:
        return GenerateCoverLetterResponse(cover_letter=cached_cover_letter)

    # Check for cached job description first
    cached_jd = load_cached_job_description(request.job_url)
    job_description = cached_jd if cached_jd else request.job_description

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
        generated_cv = request.generated_cv
        if generated_cv is None:
            cached_cv = load_cached_generated_cv(request.job_url)
            if cached_cv is not None:
                generated_cv = cached_cv.model_dump(mode="json")

        messages = build_cover_letter_messages(
            page_title=request.page_title,
            job_url=request.job_url,
            job_description=job_description,
            cv_variants=[variant.model_dump(mode="json") for variant in cv_variants],
            generated_cv=generated_cv,
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


def generate_cv_content_with_usage(request: GenerateCvRequest) -> tuple[CvData, Optional[LLMUsage]]:
    """
    Generate CV and return both the CV data and token usage information.
    Used for payment tracking.
    """
    cached_cv = load_cached_generated_cv(request.job_url)
    if cached_cv is not None:
        return cached_cv, None  # Cached responses don't consume tokens

    # Check for cached job description first
    cached_jd = load_cached_job_description(request.job_url)
    job_description = cached_jd if cached_jd else request.job_description

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

    llm_usage = None
    try:
        messages = build_cv_messages(
            job_description=job_description,
            cv_variants=[variant.model_dump(mode="json") for variant in cv_variants],
        )
        llm_response = get_llm_service().generate_json(messages)
        generated_cv = CV_DATA_ADAPTER.validate_python(llm_response.payload)
        validated_cv = validate_generated_cv(generated_cv)
        llm_usage = llm_response.usage
        
        print(
            "Generated CV JSON:\n"
            + json.dumps(
                validated_cv.model_dump(mode="json"), indent=2, ensure_ascii=True
            )
        )
        try:
            output_directory = save_generated_cv_artifacts(
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
        return validated_cv, llm_usage
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


def generate_cover_letter_content_with_usage(
    request: GenerateCoverLetterRequest,
) -> tuple[GenerateCoverLetterResponse, Optional[LLMUsage]]:
    """
    Generate cover letter and return both the response and token usage information.
    Used for payment tracking.
    """
    cached_cover_letter = load_cached_cover_letter(request.job_url)
    if cached_cover_letter is not None:
        return GenerateCoverLetterResponse(cover_letter=cached_cover_letter), None  # Cached responses don't consume tokens

    # Check for cached job description first
    cached_jd = load_cached_job_description(request.job_url)
    job_description = cached_jd if cached_jd else request.job_description

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

    llm_usage = None
    try:
        generated_cv = request.generated_cv
        if generated_cv is None:
            cached_cv = load_cached_generated_cv(request.job_url)
            if cached_cv is not None:
                generated_cv = cached_cv.model_dump(mode="json")

        messages = build_cover_letter_messages(
            page_title=request.page_title,
            job_url=request.job_url,
            job_description=job_description,
            cv_variants=[variant.model_dump(mode="json") for variant in cv_variants],
            generated_cv=generated_cv,
            story_json=request.story_json_override,
        )
        llm_response = get_llm_service().generate_json(messages)
        cover_letter = llm_response.payload["cover_letter"]
        llm_usage = llm_response.usage
        
        if not isinstance(cover_letter, str) or not cover_letter.strip():
            raise ValueError(
                "LLM response did not include a valid cover_letter string."
            )
        try:
            output_directory = save_generated_cover_letter_artifacts(
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
        return GenerateCoverLetterResponse(cover_letter=cover_letter.strip()), llm_usage
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

