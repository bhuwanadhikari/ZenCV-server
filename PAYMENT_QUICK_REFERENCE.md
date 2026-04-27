# Payment Service - Quick Reference

## What Was Implemented

A complete payment system using Stripe that enables users to:
1. **Buy Credits**: Users purchase 3-20 EUR worth of tokens
2. **Track Usage**: Each generation costs tokens (calculated from LLM response)
3. **View Balance**: See available credits and spending history

## Core Concept

| User Payment | System Value | Your Margin |
|---|---|---|
| 1 EUR | 500k tokens | 50% |
| 10 EUR | 5M tokens | 50% |
| 20 EUR (max) | 10M tokens | 50% |

## API Endpoints Summary

### 1. Purchase Credits
```bash
POST /api/payment/create-intent
Headers: Authorization: Bearer {token}
Body: { "amount_eur": 5.00 }

Response:
{
  "client_secret": "pi_xxx_secret_xxx",
  "payment_intent_id": "pi_xxx",
  "amount_eur": "5.00",
  "tokens_available": 2500000
}
```

### 2. Confirm Payment
```bash
POST /api/payment/confirm
Headers: Authorization: Bearer {token}
Body: { "payment_intent_id": "pi_xxx" }

Response:
{
  "success": true,
  "message": "Payment confirmed. 2,500,000 tokens added to your account.",
  "tokens_purchased": 2500000,
  "total_tokens_available": 2500000
}
```

### 3. Check Balance
```bash
GET /api/payment/credits
Headers: Authorization: Bearer {token}

Response:
{
  "user_id": "user_123",
  "total_tokens_purchased": 5000000,
  "total_tokens_used": 1234567,
  "remaining_tokens": 3765433,
  "total_eur_spent": "10.00",
  "remaining_eur": "7.53"
}
```

### 4. View Usage History
```bash
GET /api/payment/usage-history?limit=50
Headers: Authorization: Bearer {token}

Shows each generation with exact tokens used
```

## Generation Endpoints (Now With Payment)

### CV Generation
```bash
POST /api/cv/generate
Headers: Authorization: Bearer {token}
Body: { job_description: "...", ... }

Success: 200 OK + CV data
Error: 402 Payment Required
  {
    "detail": "Insufficient credits. You need 45,678 tokens, but only have 12,345 remaining."
  }
```

### Cover Letter Generation
```bash
POST /api/cover-letter/generate
Headers: Authorization: Bearer {token}
Body: { job_description: "...", ... }

Success: 200 OK + Cover Letter
Error: 402 Payment Required + error message
```

## Frontend Implementation Checklist

- [ ] 1. Add "Buy Credits" button in drawer/menu
- [ ] 2. Display credit balance: `{remaining_eur} / {total_eur} EUR`
- [ ] 3. Implement Stripe card input and payment flow
- [ ] 4. Handle 402 Payment Required errors in generation endpoints
- [ ] 5. Show "Insufficient credits" dialog with link to buy more
- [ ] 6. Refresh credit balance after successful payment
- [ ] 7. Add credit usage breakdown/analytics view (optional)

## Setup Instructions

### 1. Configure Stripe Keys
```
# In .env file
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
```

Get from: https://dashboard.stripe.com/apikeys

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Test with Stripe Test Cards
- **Success**: 4242 4242 4242 4242
- **Decline**: 4000 0000 0000 0002

## How Token Deduction Works

1. User calls generation endpoint (CV/cover letter/job description)
2. Backend checks if user has enough tokens
3. If yes: generates content using LLM
4. LLM returns token usage (prompt + completion tokens)
5. Backend deducts total tokens from user's balance
6. Backend returns generated content + updated balance

**Example:**
- User has 5M tokens
- Generates CV (uses 45,678 tokens)
- Remaining: 4,954,322 tokens
- Next time shows: "4.95M / 5.00M tokens remaining"

## Database Tables

```
credit_purchases
├─ id (primary key)
├─ user_id (foreign key → users.id)
├─ amount_eur (Decimal: amount purchased)
├─ tokens_purchased (int: 500k per EUR)
├─ stripe_payment_intent_id (unique)
├─ status (pending|completed|failed|cancelled)
├─ created_at
└─ completed_at

token_usage
├─ id (primary key)
├─ user_id (foreign key → users.id)
├─ generation_type (cv|cover_letter|job_description)
├─ tokens_used (int: total deducted)
├─ prompt_tokens (int: from LLM)
├─ completion_tokens (int: from LLM)
└─ created_at

user_credits
├─ user_id (primary key, foreign key → users.id)
├─ total_tokens_purchased (int)
├─ total_tokens_used (int)
├─ total_eur_spent (Decimal)
└─ updated_at
```

## Troubleshooting

### Q: User sees "Insufficient credits"
A: User hasn't purchased credits or has used them all. Show "Buy Credits" button.

### Q: Payment not confirming
A: Check Stripe dashboard for payment status or verify payment_intent_id.

### Q: Wrong token deduction
A: All deductions are precise based on LLM response. Check token_usage table for audit trail.

### Q: Can't import Stripe module
A: Run `pip install stripe` or `pip install -r requirements.txt`

## Important Notes

1. **Precision**: Token counting is exact from LLM response (no rounding errors)
2. **Audit Trail**: Every token transaction is logged in token_usage table
3. **Caching**: Cached results don't consume tokens (only new generations do)
4. **User Validation**: All generation endpoints now require authentication
5. **Error Handling**: 402 status code indicates payment required

## For Operator/Admin

### Check User's Credit Balance
```python
from database import SessionLocal
from services.payment_service import PaymentService

db = SessionLocal()
service = PaymentService()
balance = service.get_user_credit_balance("user_id_here", db)
print(f"Remaining: {balance['remaining_tokens']} tokens ({balance['remaining_eur']} EUR)")
```

### Audit User's Token Usage
```python
history = service.get_token_usage_history("user_id_here", db, limit=100)
for record in history["usage_history"]:
    print(f"{record['created_at']}: {record['generation_type']} - {record['tokens_used']} tokens")
```

### Verify Payments
```python
purchases = service.get_credit_purchases_history("user_id_here", db, limit=100)
for purchase in purchases["purchase_history"]:
    print(f"{purchase['created_at']}: {purchase['amount_eur']} EUR ({purchase['status']})")
```
