# Frontend Integration Guide - Payment Service Technical Specification

## Overview

This document specifies the payment service APIs, data structures, and integration requirements for frontend developers. It describes WHAT needs to happen, not HOW to implement it.

---

## Part 1: Authentication Mechanism

### Bearer Token Authorization

All payment endpoints require authentication via HTTP `Authorization` header with Bearer token format:

```
Authorization: Bearer <jwt_token>
```

**Header Details:**
- Header Name: `Authorization`
- Format: `Bearer {token}`
- Token Type: JWT (JSON Web Token)
- Validation: Backend validates token signature and expiration

**Token Acquisition:**
- Obtained from Google OAuth callback endpoint
- Returned in `/api/auth/google/callback` response
- Must be stored securely in frontend (HttpOnly cookie recommended)
- Token expiration configured via `ACCESS_TOKEN_EXPIRE_MINUTES` env variable

**Authentication Failure:**
- Returns HTTP 401 Unauthorized
- Detail: "Missing authorization header" or "Invalid authorization header format"

---

## Part 2: Payment Flow Mechanism

### High-Level Flow

```
User Initiates Purchase
    ↓
Frontend → Create Payment Intent API
    ↓
Backend → Generate Stripe PaymentIntent
    ↓
Backend ← Return client_secret
    ↓
Frontend → Display Payment Form
    ↓
User Enters Card Details
    ↓
Frontend → Stripe.js Confirm Payment
    ↓
Stripe → Process Payment
    ↓
Stripe → Success/Failure to Frontend
    ↓
IF Success:
  Frontend → Confirm Payment API
       ↓
  Backend → Verify with Stripe
       ↓
  Backend → Add Credits to User
       ↓
  Frontend ← Return confirmation
       ↓
  Frontend → Display Success
```

### Step 1: Create Payment Intent

**Endpoint:** `POST /api/payment/create-intent`

**Authentication:** Required (Bearer token)

**Request Contract:**
- Content-Type: `application/json`
- Body: 
  ```json
  {
    "amount_eur": 5.00
  }
  ```
- `amount_eur` Constraints:
  - Type: Decimal/Float
  - Minimum: 3.00
  - Maximum: 20.00
  - Must be a valid EUR amount

**Response Contract (200 OK):**
```json
{
  "client_secret": "pi_1234567890_secret_abcdefghijk",
  "payment_intent_id": "pi_1234567890",
  "amount_eur": "5.00",
  "tokens_available": 2500000
}
```

**Response Field Meanings:**
- `client_secret`: Secret for Stripe.js client-side confirmation (use with Stripe.js)
- `payment_intent_id`: Unique Stripe PaymentIntent identifier (store for confirm step)
- `amount_eur`: Confirmed amount in EUR
- `tokens_available`: Number of tokens user will receive (amount_eur × 500,000)

**Error Responses:**
- `400 Bad Request`: Invalid amount (not between 3-20 EUR)
  ```json
  { "detail": "Amount must be between 3.00 and 20.00 EUR" }
  ```
- `401 Unauthorized`: Missing/invalid authentication token
- `500 Internal Server Error`: Stripe API error or server issue

**Backend Processing:**
1. Validates amount is between 3-20 EUR
2. Converts EUR to cents (amount × 100)
3. Calculates tokens: amount × 500,000
4. Creates Stripe PaymentIntent with converted amount in cents
5. Stores PaymentIntent metadata (user_id, amount_eur, tokens_to_purchase)
6. Saves to database as PENDING
7. Returns client_secret for frontend

---

### Step 2: Client-Side Payment Processing (Stripe.js)

**Frontend Responsibility:**
- Use Stripe.js library (`https://js.stripe.com/v3/`)
- Use `client_secret` from step 1
- Collect card details via Stripe Elements
- Confirm payment with Stripe using `stripe.confirmCardPayment(client_secret, {...})`

**Stripe Confirmation Response States:**
- `succeeded`: Payment successful → proceed to Step 3
- `requires_action`: Additional authentication needed (3D Secure, etc.)
- `error`: Payment declined or failed

**Card Details Requirements:**
- Card Number (PAN): 13-19 digits
- Expiry Date: MM/YY format, future date required
- CVC/CVV: 3-4 digit security code
- Cardholder Name: Optional but recommended

**Test Cards (Stripe Sandbox):**
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- Requires Auth: `4000 0025 0000 3155`

---

### Step 3: Confirm Payment with Backend

**Endpoint:** `POST /api/payment/confirm`

**Authentication:** Required (Bearer token)

**Request Contract:**
- Content-Type: `application/json`
- Body:
  ```json
  {
    "payment_intent_id": "pi_1234567890"
  }
  ```
- `payment_intent_id`: Must match the ID from Step 1

**Response Contract (200 OK):**
```json
{
  "success": true,
  "message": "Payment confirmed. 2,500,000 tokens added to your account.",
  "tokens_purchased": 2500000,
  "total_tokens_available": 2500000
}
```

**Response Field Meanings:**
- `success`: Boolean indicating successful confirmation
- `message`: Human-readable success message
- `tokens_purchased`: Tokens added in this transaction
- `total_tokens_available`: User's new total available tokens

**Error Responses:**
- `400 Bad Request`: Payment not found or not succeeded
  ```json
  { "detail": "Payment status is pending, expected 'succeeded'" }
  ```
- `401 Unauthorized`: Not authenticated
- `500 Internal Server Error`: Backend processing error

**Backend Processing:**
1. Retrieves PaymentIntent from database using payment_intent_id
2. Verifies it matches authenticated user_id
3. Queries Stripe API to confirm payment status
4. Validates status is "succeeded"
5. Updates PaymentIntent record: status = COMPLETED, completed_at = now
6. Gets or creates UserCredit record
7. Increments: total_tokens_purchased, total_eur_spent
8. Returns updated balance

---

## Part 3: Credit Balance Retrieval

### Display Current Credits

**Endpoint:** `GET /api/payment/credits`

**Authentication:** Required (Bearer token)

**Request Contract:**
- Method: GET
- No request body
- No query parameters

**Response Contract (200 OK):**
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

**Response Field Meanings:**
- `user_id`: Authenticated user's unique identifier
- `total_tokens_purchased`: Lifetime tokens purchased across all transactions
- `total_tokens_used`: Tokens consumed by all generations
- `remaining_tokens`: Available tokens = purchased - used (never negative)
- `total_eur_spent`: Sum of all EUR spent on credits
- `remaining_eur`: EUR equivalent of remaining tokens (for UI display)

**Display Format for Drawer:**
- Primary: `{remaining_eur} / {total_eur_spent} EUR`
- Example: `"7.53 / 10.00 EUR"` (means 7.53 EUR remaining, 10.00 EUR total purchased)
- Alternative: `({remaining_tokens / 1000000}.toFixed(2))M tokens remaining`

**Calculation Details:**
- remaining_eur = remaining_tokens / 500,000 (since 1 EUR = 500k tokens to user)
- remaining_tokens = total_tokens_purchased - total_tokens_used

**Error Responses:**
- `401 Unauthorized`: Not authenticated
- `500 Internal Server Error`: Database query error

---

## Part 4: Generation with Credit Validation

### CV Generation with Credits

**Endpoint:** `POST /api/cv/generate`

**Authentication:** Required (Bearer token)

**Request Contract:**
- Content-Type: `application/json`
- Body: [Standard CV generation request schema]

**Pre-Execution Check:**
Backend performs these checks before generation:
1. Verifies user is authenticated
2. Queries user's credit balance
3. Estimates tokens needed (varies per request)
4. Compares: remaining_tokens ≥ tokens_estimated?
   - If YES: Proceeds with generation
   - If NO: Rejects with 402

**Success Response (200 OK):**
Returns generated CV data (standard response)

**Insufficient Credits Response (402 Payment Required):**
```json
{
  "detail": "Insufficient credits. You need 45,678 tokens, but only have 12,345 remaining."
}
```

**Response Field Meanings:**
- Status Code: `402` (HTTP Payment Required)
- `detail`: Specific error explaining:
  - Tokens needed for this generation
  - Tokens currently available
  - Clear action (user must buy credits)

**Backend Execution Flow (if sufficient credits):**
1. Calls LLM to generate CV
2. LLM returns response + token usage (prompt_tokens + completion_tokens)
3. Records token usage in token_usage table:
   - generation_type = "cv"
   - tokens_used = prompt_tokens + completion_tokens
   - timestamp = now
4. Updates UserCredit: total_tokens_used += tokens_used
5. Calculates new balance: remaining = purchased - used
6. Returns generated CV + remaining balance info (optional in response)

### Cover Letter Generation with Credits

**Endpoint:** `POST /api/cover-letter/generate`

**Same mechanism as CV generation:**
- Same credit checking flow
- Same 402 error for insufficient credits
- Same token deduction logic
- generation_type = "cover_letter" in token_usage

---

## Part 5: Token Usage History

### View Generation History

**Endpoint:** `GET /api/payment/usage-history?limit=50`

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `limit` (optional): Maximum records to return
  - Type: Integer
  - Default: 50
  - Maximum: 100 (recommended)

**Response Contract (200 OK):**
```json
{
  "total_usage": 125,
  "usage_history": [
    {
      "id": "usage_uuid_1",
      "user_id": "user_123",
      "generation_type": "cv",
      "tokens_used": 45678,
      "prompt_tokens": 2345,
      "completion_tokens": 43333,
      "created_at": "2024-01-15T10:30:00"
    },
    {
      "id": "usage_uuid_2",
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

**Response Field Meanings:**
- `total_usage`: Total number of usage records for user (across all time)
- `usage_history`: Array of usage records (ordered by most recent first)
- `total_records`: Number of records in this response

**Record Field Meanings:**
- `id`: Unique identifier for this usage record
- `generation_type`: One of: `"cv"`, `"cover_letter"`, `"job_description"`
- `tokens_used`: Total tokens consumed (prompt + completion)
- `prompt_tokens`: Tokens in the input prompt to LLM
- `completion_tokens`: Tokens in LLM's response
- `created_at`: ISO 8601 timestamp of generation

**Calculation Verification:**
- tokens_used should equal prompt_tokens + completion_tokens (audit trail)

**Error Responses:**
- `401 Unauthorized`: Not authenticated
- `500 Internal Server Error`: Database query error

---

## Part 6: Credit Purchase History

### View Payment Transactions

**Endpoint:** `GET /api/payment/purchase-history?limit=50`

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `limit` (optional): Maximum records to return (default: 50)

**Response Contract (200 OK):**
```json
{
  "total_purchases": 3,
  "purchase_history": [
    {
      "id": "purchase_uuid_1",
      "user_id": "user_123",
      "amount_eur": "5.00",
      "tokens_purchased": 2500000,
      "stripe_payment_intent_id": "pi_1234567890",
      "status": "completed",
      "created_at": "2024-01-15T10:30:00",
      "completed_at": "2024-01-15T10:30:05"
    }
  ],
  "total_records": 1
}
```

**Response Field Meanings:**
- `total_purchases`: Total number of purchase records for user
- `purchase_history`: Array of purchase records (most recent first)

**Purchase Record Fields:**
- `id`: Unique purchase identifier
- `amount_eur`: Amount paid in EUR
- `tokens_purchased`: Tokens added from this purchase
- `stripe_payment_intent_id`: Stripe reference ID
- `status`: One of: `"pending"`, `"completed"`, `"failed"`, `"cancelled"`
- `created_at`: When purchase was initiated
- `completed_at`: When payment was confirmed (null if not completed)

**Status Meanings:**
- `pending`: Payment initiated but not yet confirmed
- `completed`: Payment successful and tokens added
- `failed`: Payment processing failed
- `cancelled`: User cancelled the payment

---

## Part 7: Error Handling & Status Codes

### HTTP Status Codes

| Code | Name | Cause | Action |
|------|------|-------|--------|
| 200 | OK | Successful operation | Proceed normally |
| 400 | Bad Request | Invalid amount, missing fields | Show validation error |
| 401 | Unauthorized | Missing/invalid token | Redirect to login |
| 402 | Payment Required | Insufficient credits | Show "Buy Credits" dialog |
| 500 | Internal Server Error | Server/Stripe error | Show generic error, retry |

### Payment-Specific Error Scenarios

**Scenario 1: Insufficient Credits Before Generation**
- Status: 402 Payment Required
- Action: Show error message with tokens needed/available
- UI: Offer "Buy Credits" button in error dialog
- Data: remaining_tokens provided for display

**Scenario 2: Payment Amount Out of Range**
- Status: 400 Bad Request
- Action: Show validation error
- UI: Enforce min (3 EUR) and max (20 EUR) in input field

**Scenario 3: Payment Already Confirmed**
- Status: 200 OK (idempotent)
- Action: Return success message "Already confirmed"
- Data: Return current balance instead of re-processing

**Scenario 4: Stripe API Timeout**
- Status: 500 Internal Server Error
- Action: Suggest retry after delay
- UI: Show "Try again" button with retry logic

---

## Part 8: Token Economics Summary

### Conversion Rates

- **Purchase to User Tokens**: 1 EUR → 500,000 tokens
- **Minimum Purchase**: 3 EUR → 1,500,000 tokens
- **Maximum Purchase**: 20 EUR → 10,000,000 tokens
- **Your System Cost**: 1 EUR → 1,000,000 tokens API usage
- **Your Margin**: 50% (500,000 tokens retained per EUR)

### Token Cost Examples

| Generation | Est. Tokens | EUR Cost | User EUR/Token |
|---|---|---|---|
| CV (typical) | 45,000 | ~0.09 EUR | 1 token ≈ 0.000002 EUR |
| Cover Letter (typical) | 23,000 | ~0.046 EUR | 1 token ≈ 0.000002 EUR |
| Job Description (typical) | 15,000 | ~0.03 EUR | 1 token ≈ 0.000002 EUR |

### Balance Calculation

```
remaining_tokens = total_tokens_purchased - total_tokens_used
remaining_eur = remaining_tokens / 500,000
spent_percentage = (total_tokens_used / total_tokens_purchased) * 100
```

---

## Part 9: UI Requirements (No Implementation Code)

### Drawer/Navigation Display

**Location:** Drawer or top navigation bar

**Required Information:**
- Credit balance in format: `{remaining_eur} / {total_eur_spent} EUR`
- Optional: Remaining tokens in millions: `{remaining_tokens / 1000000}M tokens`
- Optional: Visual progress bar showing percentage spent

**Update Frequency:**
- On app load/login
- After successful payment
- After each generation (to reflect deduction)
- Optional: Periodic refresh every 30-60 seconds

### Buy Credits Dialog

**Trigger:**
- User clicks "Buy Credits" button
- User attempts generation with insufficient credits (402 response)

**Required Elements:**
- Amount selector: Pre-defined packages (3, 5, 10, 20 EUR) or custom input
- Input validation: Enforce 3-20 EUR range
- Display: Show tokens available for selected amount
- Stripe card form: Cardholder name, card number, expiry, CVC
- Submit button: "Pay {amount} EUR"

**Data Display:**
- Amount in EUR
- Equivalent tokens: `amount × 500,000`
- Confirmation message after success

### Generation Failure Handling

**Insufficient Credits Error Dialog:**
- Show error message from 402 response
- Display tokens needed vs. available
- Offer "Buy Credits" button to open payment dialog
- Alternative: Redirect to credits page

### Usage History View (Optional)

**Display Requirements:**
- Table or list of generation records
- Columns: Type (CV/Cover Letter), Tokens Used, Date
- Sortable by date (most recent first)
- Pagination or "Load More" for large histories

### Purchase History View (Optional)

**Display Requirements:**
- Table or list of payment transactions
- Columns: Amount (EUR), Tokens, Status, Date
- Status badges: completed (green), pending (yellow), failed (red)
- Filter by status if possible

---

## Part 10: Testing Checklist

**Payment Flow Testing:**
- [ ] Can create payment intent with valid amounts (3, 5, 10, 20 EUR)
- [ ] Rejects invalid amounts (<3, >20 EUR) with 400 error
- [ ] Stripe test card 4242... results in successful payment
- [ ] Stripe test card 4000...0002 results in decline
- [ ] Can confirm payment after Stripe succeeds
- [ ] Confirming twice is idempotent (same response)

**Balance & Tracking:**
- [ ] Balance shown after successful payment
- [ ] Tokens deducted correctly after each generation
- [ ] Token count is precise (no rounding errors)
- [ ] Usage history records all generations
- [ ] Purchase history shows all transactions

**Error Scenarios:**
- [ ] 401 returned when token missing
- [ ] 402 returned when insufficient credits
- [ ] 400 returned for invalid amount
- [ ] Error messages are clear and actionable

**UI/UX:**
- [ ] Credit balance updates without page reload
- [ ] Payment dialog appears when needed
- [ ] Insufficient credits prevents generation
- [ ] Success message shown after payment
- [ ] History views load without freezing

---

## Appendix: Response Model Schemas

### UserCreditResponse

```json
{
  "user_id": "string",
  "total_tokens_purchased": "integer",
  "total_tokens_used": "integer",
  "remaining_tokens": "integer",
  "total_eur_spent": "string (decimal)",
  "remaining_eur": "string (decimal)"
}
```

### TokenUsageResponse

```json
{
  "id": "string (UUID)",
  "user_id": "string",
  "generation_type": "string (cv|cover_letter|job_description)",
  "tokens_used": "integer",
  "prompt_tokens": "integer",
  "completion_tokens": "integer",
  "created_at": "string (ISO 8601)"
}
```

### CreditPurchaseResponse

```json
{
  "id": "string (UUID)",
  "user_id": "string",
  "amount_eur": "string (decimal)",
  "tokens_purchased": "integer",
  "stripe_payment_intent_id": "string",
  "status": "string (pending|completed|failed|cancelled)",
  "created_at": "string (ISO 8601)",
  "completed_at": "string (ISO 8601, nullable)"
}
```

---

**This specification provides all technical details needed to integrate the payment service. Refer to the API contract for exact request/response formats and status codes.**
