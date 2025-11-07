# app/auth.py
# Lightweight JWT + TOTP scaffolding for admin / terminal users.
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from app.config import settings
import pyotp

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd.verify(pw, hashed)

def create_jwt(subject: str, roles: list = None, expires_minutes: int = 60):
    now = datetime.utcnow()
    payload = {"sub": subject, "roles": roles or [], "iat": now.timestamp(), "exp": (now+timedelta(minutes=expires_minutes)).timestamp()}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def verify_jwt(token: str):
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])

def generate_totp_secret():
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
