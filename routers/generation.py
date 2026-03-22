import logging

from fastapi import APIRouter, HTTPException

from schemas.generation_schema import (
    CvData,
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GenerateCvRequest,
    ProcessCvHtmlRequest,
    ProcessedCvHtmlResponse,
)
from services.generation_service import (
    generate_cover_letter_content,
    generate_cv_content,
    process_cv_html_content,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/cv/generate", response_model=CvData)
def generate_cv(request: GenerateCvRequest) -> CvData:
    try:
        return generate_cv_content(request)
    except HTTPException:
        logger.exception("CV generation route failed.")
        raise
    except Exception:
        logger.exception("Unexpected error in CV generation route.")
        raise


@router.post(
    "/api/job-description/process", response_model=ProcessedCvHtmlResponse
)
def process_job_description(
    request: ProcessCvHtmlRequest,
) -> ProcessedCvHtmlResponse:
    try:
        return process_cv_html_content(request)
    except HTTPException:
        logger.exception("Job description processing route failed.")
        raise
    except Exception:
        logger.exception("Unexpected error in job description processing route.")
        raise


@router.post("/api/cover-letter/generate", response_model=GenerateCoverLetterResponse)
def generate_cover_letter(
    request: GenerateCoverLetterRequest,
) -> GenerateCoverLetterResponse:
    try:
        return generate_cover_letter_content(request)
    except HTTPException:
        logger.exception("Cover letter generation route failed.")
        raise
    except Exception:
        logger.exception("Unexpected error in cover letter generation route.")
        raise
