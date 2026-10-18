"""Local JWT authentication with PBKDF2-based salted password hashing."""
import os, hashlib, hmac
from datetime import datetime, timezone, timedelta
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import JWT_SECRET, TOKEN_EXP_MINUTES
from app.database.db import get_db
from app.database.models import User

bearer = HTTPBearer(auto_error=False)

def hash_password(password: str):
    if len(password) < 12: raise ValueError('Password must be at least 12 characters')
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 400000)
    return 'pbkdf2_sha256$400000$' + salt.hex() + '$' + derived.hex()

def verify_password(password, encoded):
    try:
        algo, iterations, salt, digest = encoded.split('$')
        if algo != 'pbkdf2_sha256': return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError): return False

def token_for(user):
    if len(JWT_SECRET) < 32 or 'REPLACE_WITH' in JWT_SECRET: raise RuntimeError('Missing JWT_SECRET; see .env.example')
    return jwt.encode({'sub':user.id, 'exp':datetime.now(timezone.utc)+timedelta(minutes=TOKEN_EXP_MINUTES)},JWT_SECRET,algorithm='HS256')

def current_user(credentials: HTTPAuthorizationCredentials | None=Depends(bearer), db:Session=Depends(get_db)):
    if not credentials: raise HTTPException(401,'Authentication required')
    try: subject=jwt.decode(credentials.credentials,JWT_SECRET,algorithms=['HS256'])['sub']
    except (jwt.PyJWTError, KeyError): raise HTTPException(401,'Invalid or expired token')
    user=db.get(User,subject)
    if not user or not user.active: raise HTTPException(401,'Account unavailable')
    return user

def admin(user:User=Depends(current_user)):
    if user.role != 'admin': raise HTTPException(403,'Administrator required')
    return user
