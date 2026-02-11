# backend/app/auth/security.py
from passlib.context import CryptContext
from jose import jwt
import pyotp, os, time

SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_ME")
ALGO = "HS256"

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)

def create_jwt(sub: str, role: str):
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + 1800
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)

def gen_totp_secret():
    return pyotp.random_base32()

def verify_totp(secret: str, code: str):
    return pyotp.TOTP(secret).verify(code, valid_window=1)
