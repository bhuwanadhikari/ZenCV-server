# Payment Service Implementation Guide

## Overview

The payment service enables users to purchase credits before using the CV, cover letter, and job description generation features. Each user must have sufficient credits to perform generation operations.

### Token Economics

- **User Purchase**: 1 EUR = 500,000 tokens available to user
  - Minimum purchase: 3 EUR = 1.5M tokens
  - Maximum purchase: 20 EUR = 10M tokens
- **System Margin**: 
  - ChatGPT API costs: 1 EUR = 1M tokens usage
  - User allocation: 500k tokens
  - Margin: 50% (500k tokens = ~50% margin)

### Payment Flow

1. User clicks "Buy Credits" on frontend
2. Frontend calls `POST /api/payment/create-intent` with EUR amount
3. Backend creates Stripe PaymentIntent and returns client_secret
4. Frontend uses Stripe.js to confirm payment
5. Frontend calls `POST /api/payment/confirm` with payment_intent_id
6. Backend verifies payment and adds credits to user account

### Generation Flow with Payment

1. User requests CV/cover letter/job description generation
2. Backend checks if user has sufficient credits for the estimated token usage
3. If insufficient, return HTTP 402 with credit information
4. If sufficient, proceed with generation
5. After successful generation, deduct tokens from user's balance
6. Return generated content and updated credit balance

## Setup Instructions

### 1. Stripe Setup

1. Create a Stripe account at https://stripe.com
2. Get your API keys from https://dashboard.stripe.com/apikeys
3. You'll need:
   - Publishable Key (pk_test_... or pk_live_...)
   - Secret Key (sk_test_... or sk_live_...)
4. Add these to your `.env` file:

```env
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
```

### 2. Database Setup

The payment service uses three new database tables:

- `credit_purchases` - Tracks Stripe payment transactions
- `token_usage` - Tracks token consumption per generation
- `user_credits` - Tracks user's current credit balance

These tables are automatically created when the app initializes.

### 3. Environment Variables

```env
# Required Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
```

## API Endpoints

### 1. Create Payment Intent

**Endpoint**: `POST /api/payment/create-intent`

**Authentication**: Required (Bearer token)

**Request Body**:
```json
{
  "amount_eur": 5.00
}
```

**Parameters**:
- `amount_eur` (number, required): Amount in EUR (minimum: 3.00, maximum: 20.00)

**Response** (200 OK):
```json
{
  "client_secret": "pi_xxxxx_secret_xxxxx",
  "payment_intent_id": "pi_xxxxx",
  "amount_eur": "5.00",
  "tokens_available": 2500000
}
```

**Error Responses**:
- `400 Bad Request`: Invalid amount (not between 3-20 EUR)
- `401 Unauthorized`: Not authenticated
- `500 Internal Server Error`: Stripe API error

**Frontend Implementation Example**:
```javascript
const response = await fetch('/api/payment/create-intent', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ amount_eur: 5.00 }),
});

const data = await response.json();
const { client_secret, amount_eur, tokens_available } = data;

// Use Stripe.js to confirm payment
const result = await stripe.confirmCardPayment(client_secret, {
  payment_method: {
    card: cardElement,
    billing_details: { name: userName },
  },
});

if (result.paymentIntent.status === 'succeeded') {
  // Call confirm endpoint
}
```

---

### 2. Confirm Payment

**Endpoint**: `POST /api/payment/confirm`

**Authentication**: Required (Bearer token)

**Request Body**:
```json
{
  "payment_intent_id": "pi_xxxxx"
}
```

**Parameters**:
- `payment_intent_id` (string, required): Stripe payment intent ID from create-intent response

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Payment confirmed. 2,500,000 tokens added to your account.",
  "tokens_purchased": 2500000,
  "total_tokens_available": 2500000
}
```

**Error Responses**:
- `400 Bad Request`: Payment not found or not succeeded
- `401 Unauthorized`: Not authenticated
- `500 Internal Server Error`: Error processing payment

---

### 3. Get Credit Balance

**Endpoint**: `GET /api/payment/credits`

**Authentication**: Required (Bearer token)

**Response** (200 OK):
```json
{
  "user_id": "user_123",
  "total_tokens_purchased": 5000000,
  "total_tokens_used": 1234567,
  "remaining_tokens": 3765433,
  "total_eur_spent": "10.00",
  "remaining_eur": "7.53"
}
```

**Display Format for Frontend**:
- Show remaining EUR and total EUR spent: `7.53 / 10.00 EUR spent`
- Or show percentage: `75.3% of credits used`

---

### 4. Get Token Usage History

**Endpoint**: `GET /api/payment/usage-history?limit=50`

**Authentication**: Required (Bearer token)

**Query Parameters**:
- `limit` (integer, optional): Maximum records to return (default: 50, max: 100)

**Response** (200 OK):
```json
{
  "total_usage": 125,
  "usage_history": [
    {
      "id": "usage_123",
      "user_id": "user_123",
      "generation_type": "cv",
      "tokens_used": 45678,
      "prompt_tokens": 2345,
      "completion_tokens": 43333,
      "created_at": "2024-01-15T10:30:00"
    },
    {
      "id": "usage_124",
      "user_id": "user_123",
      "generation_type": "cover_letter",
      "tokens_used": 23456,
      "prompt_tokens": 1234,
      "completion_tokens": 22222,
      "created_at": "2024-01-15T10:25:00"
    }
  ],
  "total_records": 2
}
```

**Generation Types**: `cv`, `cover_letter`, `job_description`

---

### 5. Get Purchase History

**Endpoint**: `GET /api/payment/purchase-history?limit=50`

**Authentication**: Required (Bearer token)

**Query Parameters**:
- `limit` (integer, optional): Maximum records to return (default: 50, max: 100)

**Response** (200 OK):
```json
{
  "total_purchases": 3,
  "purchase_history": [
    {
      "id": "purchase_123",
      "user_id": "user_123",
      "amount_eur": "5.00",
      "tokens_purchased": 2500000,
      "stripe_payment_intent_id": "pi_xxxxx",
      "status": "completed",
      "created_at": "2024-01-15T10:30:00",
      "completed_at": "2024-01-15T10:30:05"
    }
  ],
  "total_records": 1
}
```

**Status Values**: `pending`, `completed`, `failed`, `cancelled`

---

## Generation Endpoints (Updated)

### Generate CV

**Endpoint**: `POST /api/cv/generate`

**Authentication**: Required (Bearer token)

**Changes**:
- Now requires authentication
- Checks if user has sufficient credits before generation
- Deducts tokens after successful generation
- Returns HTTP 402 if insufficient credits

**Error Response** (402 Payment Required):
```json
{
  "detail": "Insufficient credits. You need 45,678 tokens, but only have 12,345 remaining."
}
```

---

### Generate Cover Letter

**Endpoint**: `POST /api/cover-letter/generate`

**Authentication**: Required (Bearer token)

**Changes**:
- Now requires authentication
- Checks if user has sufficient credits before generation
- Deducts tokens after successful generation
- Returns HTTP 402 if insufficient credits

---

## Frontend Integration Guide

### 1. Display Credit Balance in Drawer

```javascript
// Fetch user's credit balance
async function fetchCreditBalance(token) {
  const response = await fetch('/api/payment/credits', {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  return response.json();
}

// Display in drawer
function displayCredits(balance) {
  const remainingEur = parseFloat(balance.remaining_eur);
  const totalEur = parseFloat(balance.total_eur_spent);
  
  return `${remainingEur.toFixed(2)} / ${totalEur.toFixed(2)} EUR`;
  // Example: "7.53 / 10.00 EUR"
}
```

### 2. Handle Payment Required Error

```javascript
async function generateCV(request, token) {
  const response = await fetch('/api/cv/generate', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (response.status === 402) {
    const error = await response.json();
    // Show "Insufficient credits" message to user
    showDialog('Buy Credits', error.detail);
    return null;
  }

  return response.json();
}
```

### 3. Stripe.js Integration

```html
<script src="https://js.stripe.com/v3/"></script>

<script>
const stripe = Stripe('pk_test_your_publishable_key');
const elements = stripe.elements();
const cardElement = elements.create('card');
cardElement.mount('#card-element');

async function buyCredits(amount_eur) {
  // Step 1: Create payment intent
  const response = await fetch('/api/payment/create-intent', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ amount_eur }),
  });

  const { client_secret, payment_intent_id } = await response.json();

  // Step 2: Confirm payment with Stripe
  const result = await stripe.confirmCardPayment(client_secret, {
    payment_method: {
      card: cardElement,
      billing_details: { name: userName },
    },
  });

  if (result.error) {
    console.error('Payment failed:', result.error.message);
  } else if (result.paymentIntent.status === 'succeeded') {
    // Step 3: Confirm with backend
    const confirmResponse = await fetch('/api/payment/confirm', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ payment_intent_id }),
    });

    const confirmData = await confirmResponse.json();
    console.log(`Successfully added ${confirmData.tokens_purchased:,} tokens!`);
    
    // Refresh credit balance
    await fetchCreditBalance(token);
  }
}
</script>
```

## Token Calculation Details

### Why Precise Token Counting?

Since the token economics allow you to keep 50% margin:
- User pays: 1 EUR per 500k tokens
- Your API cost: 1 EUR per 1M tokens
- Net margin: 0.5 EUR per 500k tokens (50%)

**Precision is critical to avoid losses**. Always use the total tokens from LLM responses.

### Token Sources

For each generation, we track:
- `prompt_tokens`: Tokens in the input prompt
- `completion_tokens`: Tokens in the LLM response
- `total_tokens`: prompt_tokens + completion_tokens

The `total_tokens` is what gets deducted from user's balance.

### Token Usage Recording

All token usage is logged in the `token_usage` table with:
- Generation type (cv, cover_letter, job_description)
- Exact token counts
- Timestamp
- User ID

This creates an audit trail for verification.

## Security Considerations

1. **Always verify on backend**: Don't trust client-side token counting
2. **Stripe webhook verification**: Consider implementing webhook verification for additional security
3. **Rate limiting**: Consider rate limiting generation endpoints to prevent abuse
4. **Audit logs**: All token deductions are logged in token_usage table
5. **SSL/TLS**: Always use HTTPS in production for Stripe integration

## Monitoring and Debugging

### Check User's Credit Balance

```python
from database import SessionLocal
from services.payment_service import PaymentService

db = SessionLocal()
payment_service = PaymentService()
balance = payment_service.get_user_credit_balance("user_id", db)
print(balance)
```

### View Token Usage History

```python
history = payment_service.get_token_usage_history("user_id", db, limit=10)
for record in history["usage_history"]:
    print(f"{record['generation_type']}: {record['tokens_used']} tokens")
```

### Test with Stripe Test Keys

Stripe provides test card numbers for testing:
- **Success**: 4242 4242 4242 4242
- **Decline**: 4000 0000 0000 0002
- **Auth Required**: 4000 0025 0000 3155

See: https://stripe.com/docs/testing

## Troubleshooting

### "Stripe API key not configured"
- Ensure STRIPE_SECRET_KEY is set in .env file
- Verify you're using a valid Stripe secret key (starts with sk_)

### "Insufficient credits" error
- User hasn't purchased credits yet
- Previously used tokens have consumed their balance
- Check usage history: GET /api/payment/usage-history

### Payment not confirming
- Check Stripe dashboard for payment status
- Verify payment_intent_id is correct
- Ensure user_id matches the authenticated user

## Next Steps

1. Configure Stripe API keys in .env
2. Test payment flow with Stripe test keys
3. Implement frontend buy credits button
4. Display credit balance in drawer
5. Handle 402 errors in generation endpoints
6. Deploy to production with live Stripe keys
