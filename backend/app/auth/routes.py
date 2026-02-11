# backend/app/auth/routes.py
from fastapi import APIRouter, HTTPException
from jose import jwt
import pyotp
import qrcode
import io
import base64

from .security import (
    hash_password,
    verify_password,
    create_jwt,
    gen_totp_secret,
    verify_totp,
    SECRET_KEY,
    ALGO,
)

router = APIRouter(prefix="/auth")

# TEMP in-memory store (will be DB later)
USERS = {
    "admin@rutlandprojects.com": {
        "password": hash_password("Temp@123456"),
        "role": "admin",
        "mfa_enabled": False,
        "mfa_secret": None,
    }
}


@router.post("/login")
def login(data: dict):
    email = data.get("email")
    password = data.get("password")

    user = USERS.get(email)
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # If MFA enabled → require TOTP
    if user["mfa_enabled"]:
        tmp_token = create_jwt(email, "tmp")
        return {
            "mfa_required": True,
            "tmp_token": tmp_token,
        }

    # No MFA yet (first login)
    return {
        "mfa_required": False,
        "token": create_jwt(email, user["role"]),
    }


@router.post("/mfa/verify")
def mfa_verify(data: dict):
    tmp_token = data.get("tmp_token")
    code = data.get("code")

    try:
        payload = jwt.decode(tmp_token, SECRET_KEY, algorithms=[ALGO])
        email = payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid temp token")

    user = USERS.get(email)
    if not user or not verify_totp(user["mfa_secret"], code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    return {
        "token": create_jwt(email, user["role"])
    }


@router.get("/mfa/setup")
def mfa_setup(email: str):
    user = USERS.get(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    secret = gen_totp_secret()
    user["mfa_secret"] = secret

    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name="Rutland PSP"
    )

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "qr": f"data:image/png;base64,{qr_b64}"
    }


@router.post("/mfa/confirm")
def mfa_confirm(data: dict):
    email = data.get("email")
    code = data.get("code")

    user = USERS.get(email)
    if not user or not verify_totp(user["mfa_secret"], code):
        raise HTTPException(status_code=400, detail="Invalid MFA confirmation")

    user["mfa_enabled"] = True
    return {"status": "ok"}


@router.post("/password/reset")
def password_reset(data: dict):
    email = data.get("email")
    code = data.get("code")
    new_password = data.get("new_password")

    user = USERS.get(email)
    if not user or not verify_totp(user["mfa_secret"], code):
        raise HTTPException(status_code=401, detail="Invalid reset request")

    user["password"] = hash_password(new_password)
    return {"status": "password_reset"}

# --- BOOTSTRAP ADMIN USER (ONE TIME, DEV ONLY) ---
def _bootstrap_admin():
    if "admin@rutlandprojects.com" not in USERS:
        USERS["admin@rutlandprojects.com"] = {
            "password": hash_password("Temp@123456"),
            "role": "admin",
            "mfa_enabled": False,
            "mfa_secret": None,
        }

_bootstrap_admin()
