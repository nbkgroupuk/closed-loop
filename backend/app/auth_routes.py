from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

# This router handles /api/auth/*
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    """
    Super simple hard-coded login so UI can work:
      email:    admin
      password: Br_3339
    Later you can replace this with a real user table.
    """
    if not (data.email == "admin" and data.password == "Br_3339"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Dummy token – just something the frontend can store
    return LoginResponse(access_token="dummy-admin-token")
