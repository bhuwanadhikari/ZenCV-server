from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional


class CreatePaymentIntentRequest(BaseModel):
    """Request to create a Stripe payment intent"""
    amount_eur: Decimal = Field(..., ge=Decimal("3.00"), le=Decimal("20.00"), description="Amount in EUR (3-20)")


class CreatePaymentIntentResponse(BaseModel):
    """Response after creating payment intent"""
    client_secret: str = Field(..., description="Stripe client secret for frontend")
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")
    amount_eur: Decimal = Field(..., description="Amount in EUR")
    tokens_available: int = Field(..., description="Number of tokens that will be available (500k per EUR)")


class ConfirmPaymentRequest(BaseModel):
    """Request to confirm payment after Stripe succeeds"""
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")


class ConfirmPaymentResponse(BaseModel):
    """Response after confirming payment"""
    success: bool
    message: str
    tokens_purchased: int
    total_tokens_available: int


class UserCreditResponse(BaseModel):
    """Response with user's credit information"""
    user_id: str
    total_tokens_purchased: int = Field(..., description="Total tokens purchased (500k per EUR)")
    total_tokens_used: int = Field(..., description="Total tokens consumed")
    remaining_tokens: int = Field(..., description="Remaining tokens available")
    total_eur_spent: Decimal = Field(..., description="Total EUR spent on credits")
    remaining_eur: Decimal = Field(..., description="Remaining EUR value of tokens")


class TokenUsageResponse(BaseModel):
    """Response with token usage record"""
    id: str
    user_id: str
    generation_type: str
    tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    created_at: str


class TokenUsageHistoryResponse(BaseModel):
    """Response with user's token usage history"""
    total_usage: int
    usage_history: list[TokenUsageResponse]
    total_records: int
