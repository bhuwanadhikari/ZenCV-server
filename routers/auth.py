import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Header
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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


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
