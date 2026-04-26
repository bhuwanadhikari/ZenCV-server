# Google Authentication & SQLite Database Setup

This document explains the Google authentication and SQLite database implementation for the ZenCV Server.

## Overview

The server now includes:
- **Google OAuth 2.0 Authentication** - User authentication via Google
- **SQLite Database** - User data persistence
- **JWT Tokens** - Secure token-based authentication
- **User Management** - User model with tracking of creation and updates

## Setup Instructions

### 1. Install Dependencies

The required packages have been added to `requirements.txt`. Install them:

```bash
pip install -r requirements.txt
```

### 2. Configure Google OAuth

#### Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API:
   - Go to "APIs & Services" → "Library"
   - Search for "Google+ API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URIs:
     - `http://localhost:8000/api/auth/google/callback` (development)
     - Your production URL (e.g., `https://yourdomain.com/api/auth/google/callback`)
   - Copy your Client ID and Client Secret

#### Update Environment Variables

Create or update your `.env` file with the Google OAuth credentials:

```env
GOOGLE_CLIENT_ID=your_client_id_from_google_console
GOOGLE_CLIENT_SECRET=your_client_secret_from_google_console
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

# Change these in production
SECRET_KEY=your-production-secret-key
DATABASE_URL=sqlite:///./intellicv.db
```

### 3. Database Setup

The SQLite database is automatically created when the server starts. The database file will be created at `./intellicv.db`.

#### Database Schema

The `users` table includes:
- `id` - UUID primary key
- `email` - User's email (unique)
- `name` - User's full name
- `picture` - User's profile picture URL
- `google_id` - Google account ID (unique)
- `is_active` - Account status
- `created_at` - Account creation timestamp
- `updated_at` - Last update timestamp

## API Endpoints

### Authentication Endpoints

#### 1. Google OAuth Callback
**POST** `/api/auth/google/callback`

Exchange Google authorization code for JWT token.

**Request Body:**
```json
{
  "code": "authorization_code_from_google",
  "redirect_uri": "http://localhost:8000/api/auth/google/callback"
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "user": {
    "id": "user_uuid",
    "email": "user@example.com",
    "name": "User Name",
    "picture": "https://...",
    "google_id": "google_id",
    "is_active": true,
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
  }
}
```

#### 2. Get Current User
**GET** `/api/auth/me`

Get authenticated user information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": "user_uuid",
  "email": "user@example.com",
  "name": "User Name",
  "picture": "https://...",
  "google_id": "google_id",
  "is_active": true,
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:00:00"
}
```

#### 3. Logout
**POST** `/api/auth/logout`

Logout endpoint (currently stateless).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

## Frontend Integration Example

### Google Sign-In Flow

```javascript
// 1. Initiate Google Sign-In
// Include Google SDK in your HTML:
// <script src="https://accounts.google.com/gsi/client" async defer></script>

// 2. Handle the callback
async function handleGoogleSignIn(response) {
  const authCode = response.code; // Get authorization code
  
  try {
    const result = await fetch('http://localhost:8000/api/auth/google/callback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code: authCode,
        redirect_uri: 'http://localhost:8000/api/auth/google/callback'
      })
    });
    
    const data = await result.json();
    const token = data.access_token;
    
    // Store token (e.g., in localStorage or sessionStorage)
    localStorage.setItem('authToken', token);
    
    // Redirect or update UI
    console.log('User authenticated:', data.user);
  } catch (error) {
    console.error('Authentication failed:', error);
  }
}

// 3. Use token for authenticated requests
async function fetchProtectedResource() {
  const token = localStorage.getItem('authToken');
  
  const response = await fetch('http://localhost:8000/api/auth/me', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  return response.json();
}
```

## File Structure

New files created:
```
database.py                          # SQLAlchemy setup
models/user.py                       # User database model
schemas/auth_schema.py               # Auth request/response schemas
services/auth_service.py             # Authentication business logic
routers/auth.py                      # Authentication endpoints
```

Modified files:
```
main.py                              # Added database init and auth router
services/config_service.py           # Added OAuth and JWT config
requirements.txt                     # Added new dependencies
.env.example                         # Added new env variables
```

## Security Considerations

1. **Secret Key**: Change `SECRET_KEY` in production to a strong random string
2. **CORS**: Adjust `allow_origins` in main.py for production domains
3. **HTTPS**: Always use HTTPS in production for OAuth redirects
4. **Token Expiry**: Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 30)
5. **Database**: Consider using PostgreSQL instead of SQLite for production
6. **Environment Variables**: Never commit `.env` files; use `.env.example` as template

## Troubleshooting

### Database Errors
If you get database errors, delete `intellicv.db` and restart the server to recreate it.

### Google OAuth Errors
- Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct
- Verify redirect URI matches between Google Console and your `.env`
- Check that Google+ API is enabled in Google Cloud Console

### Token Validation Errors
- Ensure the token is included in the Authorization header
- Use format: `Authorization: Bearer <token>`
- Tokens expire after the configured time; refresh by re-authenticating

## Next Steps

1. Implement token refresh mechanism
2. Add user deactivation/deletion endpoints
3. Implement JWT token blacklist for logout
4. Add rate limiting to authentication endpoints
5. Migrate to PostgreSQL for production
6. Add user profile update endpoint
7. Implement two-factor authentication
