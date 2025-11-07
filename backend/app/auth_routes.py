from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.auth import verify_password, create_jwt
# Add your actual user DB logic here

router = APIRouter()

# Dummy in-memory user (replace with DB logic)
fake_user = {"username": "admin", "hashed_password": "$2b$12$123..."}  # bcrypt hash here

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(data: LoginRequest):
    if data.username != fake_user["username"] or not verify_password(data.password, fake_user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    token = create_jwt(subject=data.username)
    return {"access_token": token}
