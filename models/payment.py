from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
import enum


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationType(str, enum.Enum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    JOB_DESCRIPTION = "job_description"


class CreditPurchase(Base):
    """Store Stripe payment transactions and credit purchases"""
    __tablename__ = "credit_purchases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    amount_eur: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # Amount in Euros
    tokens_purchased: Mapped[int] = mapped_column(Integer)  # 500k tokens per EUR
    stripe_payment_intent_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount_eur": str(self.amount_eur),
            "tokens_purchased": self.tokens_purchased,
            "stripe_payment_intent_id": self.stripe_payment_intent_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TokenUsage(Base):
    """Track token consumption for each generation"""
    __tablename__ = "token_usage"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    generation_type: Mapped[str] = mapped_column(Enum(GenerationType))
    tokens_used: Mapped[int] = mapped_column(Integer)
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "generation_type": self.generation_type.value,
            "tokens_used": self.tokens_used,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "created_at": self.created_at.isoformat(),
        }


class UserCredit(Base):
    """Track user's current credit balance"""
    __tablename__ = "user_credits"

    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    total_tokens_purchased: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_eur_spent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def remaining_tokens(self) -> int:
        """Calculate remaining tokens"""
        return max(0, self.total_tokens_purchased - self.total_tokens_used)

    @property
    def remaining_eur(self) -> Decimal:
        """Calculate remaining EUR equivalent of tokens"""
        if self.total_tokens_purchased == 0:
            return Decimal("0.00")
        # Calculate how many EUR worth of tokens remain
        eur_per_token = self.total_eur_spent / Decimal(self.total_tokens_purchased)
        return Decimal(self.remaining_tokens) * eur_per_token

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "total_tokens_purchased": self.total_tokens_purchased,
            "total_tokens_used": self.total_tokens_used,
            "remaining_tokens": self.remaining_tokens,
            "total_eur_spent": str(self.total_eur_spent),
            "remaining_eur": str(self.remaining_eur),
            "updated_at": self.updated_at.isoformat(),
        }
