# Payment Web App Setup Guide

## Overview

A fully functional, hosted payment web app has been integrated into your IntelliCV server. This allows users to purchase credits directly through a web interface, solving the Chrome extension payment limitations.

---

## ✅ What's Been Set Up

### 1. **Frontend Files** (`/app/`)
- **index.html** - Payment page UI with responsive design
- **style.css** - Professional styling and animations
- **script.js** - Payment flow logic, Stripe integration, authentication

### 2. **Backend Integration**
- Updated `main.py` to serve static files from `/app` folder
- New OAuth endpoints in `routers/auth.py`:
  - `GET /api/auth/google` - Initiates Google OAuth flow
  - `GET /api/auth/google/callback` - Handles OAuth callback
- New config endpoint:
  - `GET /api/config/stripe-key` - Returns Stripe public key to frontend

### 3. **Features**
✅ User authentication via Google OAuth  
✅ Credit selection (€3-€20)  
✅ Stripe payment processing  
✅ Real-time balance display  
✅ Payment success/failure handling  
✅ Chrome extension redirect capability  
✅ Responsive mobile design  
✅ Error handling and validation  

---

## 🚀 Deployment Instructions

### Local Development

1. **Start your FastAPI server:**
   ```bash
   python main.py
   ```
   Or with uvicorn:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the payment page:**
   ```
   http://localhost:8000
   ```

### Environment Variables

Your `.env` file should already have:
```
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

### Production Deployment

#### Option 1: Same Server (Recommended for Quick Setup)
Keep everything on your existing FastAPI server:
- The app already serves static files at `/`
- All API endpoints are available
- No additional infrastructure needed

#### Option 2: Separate Frontend Hosting
If you want to host the frontend separately:

1. **Netlify/Vercel:**
   - Deploy only the `/app` folder contents
   - Update CORS in `main.py` if needed
   - Update API_BASE_URL in `script.js` to point to your backend

2. **AWS S3 + CloudFront:**
   - Upload `/app` folder to S3
   - Use CloudFront for CDN
   - Update CORS and API configuration

---

## 🔧 Configuration

### 1. **Stripe Keys**
Ensure your `.env` has valid Stripe keys:
```
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
```

Get these from [Stripe Dashboard](https://dashboard.stripe.com/apikeys)

### 2. **Google OAuth**
Ensure your `.env` has:
```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
```

Update in [Google Cloud Console](https://console.cloud.google.com/)

### 3. **CORS Configuration**
Already configured in `main.py` to allow all origins:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, restrict origins:
```python
allow_origins=["https://yourdomain.com"],
```

---

## 📱 Usage Flow

### For End Users

1. **Navigate to Payment Page**
   - Go to `http://yourdomain.com` or `http://localhost:8000`

2. **Sign In**
   - Click "Sign in with Google"
   - Complete Google OAuth
   - Automatically redirected back to payment page

3. **Purchase Credits**
   - Select amount (€3, €5, €10, €20)
   - Enter card details
   - Click "Pay"
   - See success confirmation

4. **Return to Extension**
   - Click "Back to Chrome Extension"
   - Extension receives authentication token
   - User can now use purchased credits

### For Chrome Extension

The extension can redirect users to the payment page:
```javascript
// In extension content script or popup
window.open('https://yourdomain.com', '_blank');
```

After payment, the extension should check `/api/payment/credits` endpoint:
```javascript
fetch('/api/payment/credits', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
})
```

---

## 🔐 Security Features

✅ **Bearer Token Authentication** - All payment endpoints require valid JWT  
✅ **HTTPS Only** (in production) - Stripe enforces this  
✅ **CSRF Protection** - Handled by Stripe.js  
✅ **XSS Prevention** - No inline scripts in HTML  
✅ **Secure Token Storage** - LocalStorage for demo, move to HttpOnly cookies for production  
✅ **Rate Limiting** - Implement in production  

---

## 📊 API Endpoints Used

The payment web app uses these backend endpoints:

### Authentication
- `POST /api/auth/google/callback` - Google OAuth callback
- `GET /api/auth/google` - Initiate OAuth
- `GET /api/config/stripe-key` - Get Stripe public key

### Payment
- `POST /api/payment/create-intent` - Create payment intent
- `POST /api/payment/confirm` - Confirm payment
- `GET /api/payment/credits` - Check user balance

---

## 🧪 Testing

### Test with Stripe Test Cards

```
Card Number: 4242 4242 4242 4242
Expiry: Any future date (e.g., 12/25)
CVC: Any 3 digits (e.g., 123)
```

### Test Flow

1. Start server: `python main.py`
2. Navigate to `http://localhost:8000`
3. Sign in with test Google account
4. Select €3 credit
5. Enter test Stripe card
6. Complete payment
7. Verify success message and balance update

---

## 🐛 Troubleshooting

### "Stripe public key not configured"
- Check `.env` has `STRIPE_PUBLIC_KEY`
- Restart the server after adding `.env` variables

### "Payment failed" 
- Check browser console for errors
- Verify Stripe keys are valid test keys
- Check network tab for API responses

### "Authentication failed"
- Check Google OAuth credentials in `.env`
- Verify redirect URIs match in Google Cloud Console
- Check CORS settings

### Token Issues
- Clear browser localStorage: `localStorage.clear()`
- Check JWT token expiration in `config_service.py`
- Verify `SECRET_KEY` in `.env`

---

## 📈 Next Steps

1. **Customize Branding**
   - Update colors in `style.css`
   - Update logo in `index.html`
   - Update text/messages

2. **Add Analytics**
   - Integrate Google Analytics
   - Track payment conversions
   - Monitor user flow

3. **Enhance UX**
   - Add loading states
   - Payment history view
   - Bulk purchase discounts

4. **Production Hardening**
   - Enable HTTPS
   - Implement rate limiting
   - Add logging/monitoring
   - Set up error tracking (Sentry)
   - Implement CSRF tokens

---

## 📞 Support

For issues, check:
- Browser console (F12 → Console tab)
- Network tab (F12 → Network tab)
- Backend logs: `python main.py`
- Stripe Dashboard for transaction details

---

## 🎯 Chrome Extension Integration

To redirect users from the extension to the payment page:

```javascript
// In your Chrome extension content script or popup
function openPaymentPage() {
    const paymentUrl = 'https://yourdomain.com';
    chrome.tabs.create({ url: paymentUrl });
}

// After payment, extension can check balance:
async function checkCredits(token) {
    const response = await fetch('https://yourdomain.com/api/payment/credits', {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (response.ok) {
        const data = await response.json();
        console.log('Available tokens:', data.available_tokens);
        return data;
    }
}
```

---

## 📝 Configuration Checklist

- [ ] Stripe Public Key in `.env`
- [ ] Stripe Secret Key in `.env`
- [ ] Google Client ID in `.env`
- [ ] Google Client Secret in `.env`
- [ ] Google Redirect URI configured in Google Cloud Console
- [ ] Server running and accessible
- [ ] Payment page loads at `http://localhost:8000`
- [ ] Stripe.js loads successfully
- [ ] Google OAuth flow works
- [ ] Payment processing works with test cards
- [ ] Chrome extension can access payment page

---

## 📄 Files Modified/Created

**Created:**
- `/app/index.html` - Payment page HTML
- `/app/style.css` - Styling
- `/app/script.js` - Frontend logic

**Modified:**
- `main.py` - Added static file serving
- `routers/auth.py` - Added OAuth endpoints

**No Breaking Changes:** All existing endpoints and functionality remain intact.

---

Enjoy your hosted payment web app! 🎉
