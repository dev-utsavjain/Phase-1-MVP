 # Google OAuth + JWT
 
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.config import settings

router = APIRouter()

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

def get_google_flow():
    """Create Google OAuth flow"""
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )

@router.get("/google/login")
def google_login():
    """
    Step 1: Get Google OAuth URL
    Frontend redirects user here
    """
    flow = get_google_flow()
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    return {
        "authorization_url": authorization_url,
        "state": state
    }

@router.get("/google/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Step 2: Handle Google callback
    Exchange code for tokens
    """
    flow = get_google_flow()
    flow.fetch_token(code=code)
    
    credentials = flow.credentials
    
    # Get user info
    from googleapiclient.discovery import build
    service = build('oauth2', 'v2', credentials=credentials)
    user_info = service.userinfo().get().execute()
    
    # Create or update user
    user = db.query(User).filter(User.email == user_info['email']).first()
    
    if not user:
        user = User(
            email=user_info['email'],
            full_name=user_info.get('name')
        )
        db.add(user)
    
    # Store tokens
    user.google_access_token = credentials.token
    user.google_refresh_token = credentials.refresh_token
    user.google_token_expiry = credentials.expiry
    
    db.commit()
    db.refresh(user)
    
    # Create JWT
    access_token = create_access_token(data={"sub": user.email})
    
    # Redirect to frontend with token
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name
        }
    }

@router.get("/me")
def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.full_name
    }