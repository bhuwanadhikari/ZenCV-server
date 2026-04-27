import logging
from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from services.payment_service import PaymentService
from schemas.payment_schema import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    ConfirmPaymentRequest,
    ConfirmPaymentResponse,
    UserCreditResponse,
    TokenUsageHistoryResponse,
)
from services.auth_service import get_current_user

router = APIRouter(prefix="/api/payment", tags=["payment"])
logger = logging.getLogger(__name__)


def get_payment_service() -> PaymentService:
    """Lazy load payment service to avoid initialization issues"""
    return PaymentService()



@router.post(
    "/create-intent",
    response_model=CreatePaymentIntentResponse,
    summary="Create Stripe Payment Intent",
)
def create_payment_intent(
    request: CreatePaymentIntentRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Create a Stripe payment intent for credit purchase.
    User can purchase between 3-20 EUR worth of credits.
    Each EUR purchased = 500k tokens available to user.
    """
    try:
        payment_service = get_payment_service()
        user_id = current_user["id"]
        result = payment_service.create_payment_intent(
            user_id=user_id,
            amount_eur=request.amount_eur,
            db=db,
        )
        return result
    except ValueError as e:
        logger.warning(f"Validation error in create_payment_intent: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error creating payment intent")
        raise HTTPException(status_code=500, detail="Error creating payment intent")


@router.post(
    "/confirm",
    response_model=ConfirmPaymentResponse,
    summary="Confirm Stripe Payment",
)
def confirm_payment(
    request: ConfirmPaymentRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Confirm a Stripe payment and add credits to user's account.
    Call this endpoint after Stripe confirms the payment on the frontend.
    """
    try:
        payment_service = get_payment_service()
        user_id = current_user["id"]
        result = payment_service.confirm_payment(
            user_id=user_id,
            payment_intent_id=request.payment_intent_id,
            db=db,
        )
        return result
    except ValueError as e:
        logger.warning(f"Validation error in confirm_payment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error confirming payment")
        raise HTTPException(status_code=500, detail="Error confirming payment")


@router.get(
    "/credits",
    response_model=UserCreditResponse,
    summary="Get User Credit Balance",
)
def get_credits(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Get current user's credit balance and token information.
    
    Response includes:
    - total_tokens_purchased: Total tokens purchased (500k per EUR)
    - total_tokens_used: Tokens consumed so far
    - remaining_tokens: Available tokens for use
    - total_eur_spent: Total EUR amount spent
    - remaining_eur: EUR equivalent of remaining tokens
    """
    try:
        payment_service = get_payment_service()
        user_id = current_user["id"]
        balance = payment_service.get_user_credit_balance(user_id, db)
        return balance
    except Exception as e:
        logger.exception("Error getting credit balance")
        raise HTTPException(status_code=500, detail="Error retrieving credit balance")


@router.get(
    "/usage-history",
    response_model=TokenUsageHistoryResponse,
    summary="Get Token Usage History",
)
def get_usage_history(
    limit: int = 50,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Get user's token usage history (CV, cover letter, job description generations).
    
    Query Parameters:
    - limit: Maximum number of records to return (default: 50)
    """
    try:
        payment_service = get_payment_service()
        user_id = current_user["id"]
        history = payment_service.get_token_usage_history(user_id, db, limit)
        return history
    except Exception as e:
        logger.exception("Error getting usage history")
        raise HTTPException(status_code=500, detail="Error retrieving usage history")


@router.get(
    "/purchase-history",
    summary="Get Credit Purchase History",
)
def get_purchase_history(
    limit: int = 50,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Get user's credit purchase history (Stripe transactions).
    
    Query Parameters:
    - limit: Maximum number of records to return (default: 50)
    """
    try:
        payment_service = get_payment_service()
        user_id = current_user["id"]
        history = payment_service.get_credit_purchases_history(user_id, db, limit)
        return history
    except Exception as e:
        logger.exception("Error getting purchase history")
        raise HTTPException(status_code=500, detail="Error retrieving purchase history")
