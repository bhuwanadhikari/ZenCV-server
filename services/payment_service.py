import logging
import stripe
from decimal import Decimal
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.payment import CreditPurchase, TokenUsage, UserCredit, PaymentStatus, GenerationType
from services.config_service import get_settings

logger = logging.getLogger(__name__)

# Conversion constants
TOKENS_PER_EUR = 500_000  # User gets 500k tokens per EUR (we keep 50%)
EUR_MIN = Decimal("3.00")
EUR_MAX = Decimal("20.00")


class PaymentService:
    def __init__(self):
        settings = get_settings()
        self.stripe_secret_key = settings.stripe_secret_key
        self.stripe_publishable_key = settings.stripe_publishable_key
        
        if not self.stripe_secret_key:
            raise ValueError("STRIPE_SECRET_KEY not configured")
        
        stripe.api_key = self.stripe_secret_key

    def create_payment_intent(
        self, user_id: str, amount_eur: Decimal, db: Session
    ) -> dict:
        """
        Create a Stripe payment intent for credit purchase
        
        Args:
            user_id: User ID
            amount_eur: Amount in EUR (must be between 3-20)
            db: Database session
            
        Returns:
            Dict with client_secret, payment_intent_id, amount_eur, tokens_available
        """
        if not EUR_MIN <= amount_eur <= EUR_MAX:
            raise ValueError(f"Amount must be between {EUR_MIN} and {EUR_MAX} EUR")

        try:
            # Convert EUR to cents for Stripe
            amount_cents = int(amount_eur * 100)
            tokens_to_purchase = int(amount_eur * TOKENS_PER_EUR)

            # Create Stripe payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="eur",
                metadata={
                    "user_id": user_id,
                    "amount_eur": str(amount_eur),
                    "tokens_to_purchase": tokens_to_purchase,
                },
            )

            # Store in database as pending
            purchase_id = str(uuid4())
            purchase = CreditPurchase(
                id=purchase_id,
                user_id=user_id,
                amount_eur=amount_eur,
                tokens_purchased=tokens_to_purchase,
                stripe_payment_intent_id=intent.id,
                status=PaymentStatus.PENDING,
            )
            db.add(purchase)
            db.commit()

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount_eur": str(amount_eur),
                "tokens_available": tokens_to_purchase,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise

    def confirm_payment(self, user_id: str, payment_intent_id: str, db: Session) -> dict:
        """
        Confirm a Stripe payment and add credits to user
        
        Args:
            user_id: User ID
            payment_intent_id: Stripe payment intent ID
            db: Database session
            
        Returns:
            Dict with success status and details
        """
        try:
            # Retrieve payment intent from Stripe
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Check if payment succeeded
            if intent.status != "succeeded":
                raise ValueError(f"Payment status is {intent.status}, expected 'succeeded'")

            # Find the purchase record
            purchase = db.query(CreditPurchase).filter(
                CreditPurchase.stripe_payment_intent_id == payment_intent_id,
                CreditPurchase.user_id == user_id,
            ).first()

            if not purchase:
                raise ValueError("Payment record not found")

            if purchase.status == PaymentStatus.COMPLETED:
                return {
                    "success": True,
                    "message": "Payment already confirmed",
                    "tokens_purchased": purchase.tokens_purchased,
                    "total_tokens_available": self.get_user_credit_balance(user_id, db).get(
                        "remaining_tokens", 0
                    ),
                }

            # Update purchase status
            purchase.status = PaymentStatus.COMPLETED
            purchase.completed_at = datetime.utcnow()
            db.add(purchase)

            # Get or create user credit record
            user_credit = db.query(UserCredit).filter(UserCredit.user_id == user_id).first()
            if not user_credit:
                user_credit = UserCredit(user_id=user_id)
                db.add(user_credit)

            # Update user credits
            user_credit.total_tokens_purchased += purchase.tokens_purchased
            user_credit.total_eur_spent += purchase.amount_eur
            user_credit.updated_at = datetime.utcnow()

            db.commit()

            logger.info(
                f"Payment confirmed for user {user_id}: {purchase.amount_eur} EUR, "
                f"{purchase.tokens_purchased} tokens"
            )

            return {
                "success": True,
                "message": f"Payment confirmed. {purchase.tokens_purchased:,} tokens added to your account.",
                "tokens_purchased": purchase.tokens_purchased,
                "total_tokens_available": user_credit.total_tokens_purchased - user_credit.total_tokens_used,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            raise

    def get_user_credit_balance(self, user_id: str, db: Session) -> dict:
        """
        Get user's current credit balance
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            Dict with credit information
        """
        user_credit = db.query(UserCredit).filter(UserCredit.user_id == user_id).first()

        if not user_credit:
            # Return default values for new users
            return {
                "user_id": user_id,
                "total_tokens_purchased": 0,
                "total_tokens_used": 0,
                "remaining_tokens": 0,
                "total_eur_spent": "0.00",
                "remaining_eur": "0.00",
            }

        return user_credit.to_dict()

    def check_sufficient_credits(self, user_id: str, tokens_needed: int, db: Session) -> bool:
        """
        Check if user has sufficient credits for generation
        
        Args:
            user_id: User ID
            tokens_needed: Number of tokens needed
            db: Database session
            
        Returns:
            True if user has enough credits, False otherwise
        """
        balance = self.get_user_credit_balance(user_id, db)
        return balance["remaining_tokens"] >= tokens_needed

    def deduct_tokens(
        self,
        user_id: str,
        tokens_used: int,
        prompt_tokens: int,
        completion_tokens: int,
        generation_type: GenerationType,
        db: Session,
    ) -> dict:
        """
        Deduct tokens from user's balance after generation
        
        Args:
            user_id: User ID
            tokens_used: Total tokens used
            prompt_tokens: Prompt tokens from LLM
            completion_tokens: Completion tokens from LLM
            generation_type: Type of generation (CV, COVER_LETTER, JOB_DESCRIPTION)
            db: Database session
            
        Returns:
            Dict with updated balance information
        """
        # Record token usage
        usage_id = str(uuid4())
        token_usage = TokenUsage(
            id=usage_id,
            user_id=user_id,
            generation_type=generation_type,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        db.add(token_usage)

        # Update user credit
        user_credit = db.query(UserCredit).filter(UserCredit.user_id == user_id).first()
        if not user_credit:
            raise ValueError(f"User credit record not found for user {user_id}")

        user_credit.total_tokens_used += tokens_used
        user_credit.updated_at = datetime.utcnow()
        db.add(user_credit)
        db.commit()

        logger.info(
            f"Tokens deducted for user {user_id}: {tokens_used} tokens "
            f"({generation_type.value}), remaining: {user_credit.remaining_tokens}"
        )

        return {
            "tokens_used": tokens_used,
            "remaining_tokens": user_credit.remaining_tokens,
            "remaining_eur": str(user_credit.remaining_eur),
        }

    def get_token_usage_history(
        self, user_id: str, db: Session, limit: int = 50
    ) -> dict:
        """
        Get user's token usage history
        
        Args:
            user_id: User ID
            db: Database session
            limit: Maximum number of records to return
            
        Returns:
            Dict with usage history
        """
        usage_records = (
            db.query(TokenUsage)
            .filter(TokenUsage.user_id == user_id)
            .order_by(desc(TokenUsage.created_at))
            .limit(limit)
            .all()
        )

        total_usage = db.query(TokenUsage).filter(TokenUsage.user_id == user_id).count()

        return {
            "total_usage": total_usage,
            "usage_history": [record.to_dict() for record in usage_records],
            "total_records": len(usage_records),
        }

    def get_credit_purchases_history(
        self, user_id: str, db: Session, limit: int = 50
    ) -> dict:
        """
        Get user's credit purchase history
        
        Args:
            user_id: User ID
            db: Database session
            limit: Maximum number of records to return
            
        Returns:
            Dict with purchase history
        """
        purchases = (
            db.query(CreditPurchase)
            .filter(CreditPurchase.user_id == user_id)
            .order_by(desc(CreditPurchase.created_at))
            .limit(limit)
            .all()
        )

        return {
            "total_purchases": db.query(CreditPurchase).filter(
                CreditPurchase.user_id == user_id
            ).count(),
            "purchase_history": [p.to_dict() for p in purchases],
            "total_records": len(purchases),
        }
