import logging
from datetime import datetime, timedelta
from typing import Optional
import uuid

import jwt
import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import User
from services.config_service import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def exchange_google_auth_code(code: str, redirect_uri: str) -> dict:
    """Exchange Google authorization code for tokens"""
    token_url = "https://oauth2.googleapis.com/token"
    
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth credentials not configured",
        )
    
    try:
        response = requests.post(
            token_url,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to exchange Google auth code: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate with Google",
        )


def get_google_user_info(access_token: str) -> dict:
    """Get user information from Google using access token"""
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    try:
        response = requests.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to get Google user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user information from Google",
        )


def authenticate_google_user(
    auth_code: str,
    redirect_uri: str,
    db: Session,
) -> dict:
    """Complete Google OAuth flow and create/update user"""
    
    # Exchange code for tokens
    token_data = exchange_google_auth_code(auth_code, redirect_uri)
    access_token = token_data.get("access_token")
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to obtain access token from Google",
        )
    
    # Get user info from Google
    user_info = get_google_user_info(access_token)
    
    google_id = user_info.get("id")
    email = user_info.get("email")
    name = user_info.get("name")
    picture = user_info.get("picture")
    
    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve required user information from Google",
        )
    
    # Check if user exists
    user = db.query(User).filter(User.google_id == google_id).first()
    
    if user:
        # Update existing user
        user.email = email
        user.name = name
        user.picture = picture
        user.updated_at = datetime.utcnow()
    else:
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            picture=picture,
            google_id=google_id,
            is_active=True,
        )
        db.add(user)
    
    db.commit()
    db.refresh(user)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id},
        expires_delta=access_token_expires,
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


def get_current_user(token: str, db: Session) -> User:
    """Get current user from token"""
    payload = verify_token(token)
    email: str = payload.get("sub")
    
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    user = db.query(User).filter(User.email == email).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    return user
