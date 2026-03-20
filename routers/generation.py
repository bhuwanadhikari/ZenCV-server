import logging

from fastapi import APIRouter, HTTPException

from schemas.generation_schema import (
    CvData,
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GenerateCvRequest,
)
from services.generation_service import (
    generate_cover_letter_content,
    generate_cv_content,
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
