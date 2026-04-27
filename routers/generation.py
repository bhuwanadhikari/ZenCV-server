import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.generation_schema import (
    CvData,
    GenerateCoverLetterRequest,
    GenerateCoverLetterResponse,
    GenerateCvRequest,
    ProcessCvHtmlRequest,
    ProcessedCvHtmlResponse,
)
from services.generation_service import (
    generate_cover_letter_content_with_usage,
    generate_cv_content_with_usage,
    process_cv_html_content,
)
from services.payment_service import PaymentService
from services.auth_service import get_current_user
from models.payment import GenerationType

router = APIRouter()
logger = logging.getLogger(__name__)


def get_payment_service() -> PaymentService:
    """Lazy load payment service to avoid initialization issues"""
    return PaymentService()



@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/cv/generate", response_model=CvData)
def generate_cv(
    request: GenerateCvRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CvData:
    try:
        payment_service = get_payment_service()
        user_id = current_user["id"]
        
        # Generate CV and get token usage
        generated_cv, llm_usage = generate_cv_content_with_usage(request)
        
        # Calculate tokens used (we'll use total_tokens as the cost)
        tokens_used = llm_usage.total_tokens if llm_usage else 0
        
        # Check if user has sufficient credits
        if not payment_service.check_sufficient_credits(user_id, tokens_used, db):
            balance = payment_service.get_user_credit_balance(user_id, db)
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient credits. You need {tokens_used:,} tokens, but only have {balance['remaining_tokens']:,} remaining.",
            )
        
        # Deduct tokens after successful generation
        if tokens_used > 0:
            if llm_usage:
                payment_service.deduct_tokens(
                    user_id=user_id,
                    tokens_used=tokens_used,
                    prompt_tokens=llm_usage.prompt_tokens,
                    completion_tokens=llm_usage.completion_tokens,
                    generation_type=GenerationType.CV,
                    db=db,
                )
        
        return generated_cv
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
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GenerateCoverLetterResponse:
    try:
        payment_service = get_payment_service()
        user_id = current_user["id"]
        
        # Generate cover letter and get token usage
        cover_letter_response, llm_usage = generate_cover_letter_content_with_usage(request)
        
        # Calculate tokens used
        tokens_used = llm_usage.total_tokens if llm_usage else 0
        
        # Check if user has sufficient credits
        if not payment_service.check_sufficient_credits(user_id, tokens_used, db):
            balance = payment_service.get_user_credit_balance(user_id, db)
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient credits. You need {tokens_used:,} tokens, but only have {balance['remaining_tokens']:,} remaining.",
            )
        
        # Deduct tokens after successful generation
        if tokens_used > 0:
            if llm_usage:
                payment_service.deduct_tokens(
                    user_id=user_id,
                    tokens_used=tokens_used,
                    prompt_tokens=llm_usage.prompt_tokens,
                    completion_tokens=llm_usage.completion_tokens,
                    generation_type=GenerationType.COVER_LETTER,
                    db=db,
                )
        
        return cover_letter_response
    except HTTPException:
        logger.exception("Cover letter generation route failed.")
        raise
    except Exception:
        logger.exception("Unexpected error in cover letter generation route.")
        raise
