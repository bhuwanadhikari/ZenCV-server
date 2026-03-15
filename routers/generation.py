from fastapi import APIRouter

from schemas.generation_schema import (
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GenerateCvRequest,
    GenerateCvResponse,
)
from services.generation_service import generate_cover_letter_content, generate_cv_content


router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/cv/generate", response_model=GenerateCvResponse)
def generate_cv(request: GenerateCvRequest) -> GenerateCvResponse:
    return generate_cv_content(request)


@router.post("/api/cover-letter/generate", response_model=GenerateCoverLetterResponse)
def generate_cover_letter(request: GenerateCoverLetterRequest) -> GenerateCoverLetterResponse:
    return generate_cover_letter_content(request)
