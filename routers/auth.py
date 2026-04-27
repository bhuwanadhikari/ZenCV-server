import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from schemas.auth_schema import (
    Token,
    UserResponse,
    GoogleAuthRequest,
)
from services.auth_service import (
    authenticate_google_user,
    get_current_user,
)
from services.config_service import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])
settings = get_settings()


@router.post("/google/callback", response_model=dict)
def google_callback(
    request: GoogleAuthRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Handle Google OAuth callback.
    Expects the authorization code and redirect URI.
    """
    try:
        result = authenticate_google_user(
            auth_code=request.code,
            redirect_uri=request.redirect_uri,
            db=db,
        )
        return {
            "access_token": result["access_token"],
            "token_type": result["token_type"],
            "user": result["user"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in Google callback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    authorization: str = Header(None),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Get current authenticated user information"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    
    user = get_current_user(token, db)
    return user.to_dict()


@router.post("/logout", response_model=dict)
def logout(
    authorization: str = Header(None),
):
    """
    Logout endpoint. In a real application, you might want to blacklist tokens here.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    
    return {"message": "Logged out successfully"}


# ===== Payment Web App OAuth Flow =====

@router.get("/google")
def initiate_google_login(redirect_uri: str = Query(...)):
    """
    Initiate Google OAuth flow for payment web app.
    
    Redirects to Google login page.
    
    Query Parameters:
    - redirect_uri: Where to redirect after Google authentication (e.g., http://localhost:8000/payment/callback)
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured",
        )
    
    # Build Google OAuth URL
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "access_type": "offline",
    }
    
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(None),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Handle Google OAuth callback for payment web app.
    
    This endpoint is called by Google after the user authenticates.
    Returns an access token that can be used for payment API calls.
    """
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorization code received from Google",
        )
    
    # Determine redirect URI based on request origin
    # In production, you should use a fixed redirect URI
    redirect_uri = "http://localhost:8000/api/auth/google/callback"
    
    try:
        # Authenticate with Google and create/update user
        result = authenticate_google_user(
            auth_code=code,
            redirect_uri=redirect_uri,
            db=db,
        )
        
        access_token = result["access_token"]
        
        # Redirect back to payment page with token
        # The payment page will read this token from the URL and store it
        return RedirectResponse(
            url=f"/payment?auth_token={access_token}",
            status_code=302
        )
    except HTTPException as e:
        # Redirect to payment page with error
        return RedirectResponse(
            url=f"/payment?error={e.detail}",
            status_code=302
        )

