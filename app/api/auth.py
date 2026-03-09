from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.auth import UserRegister, UserLogin, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/register")
def register(payload: UserRegister, db: Session = Depends(get_db)):

    user = AuthService.register(db, payload)

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):

    token = AuthService.login(db, payload)

    return TokenResponse(access_token=token)