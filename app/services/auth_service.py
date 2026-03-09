from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models.user import User
from app.schemas.auth import UserRegister, UserLogin
from app.core.security import hash_password, verify_password, create_access_token


class AuthService:

    @staticmethod
    def register(db: Session, payload: UserRegister):

        existing = db.query(User).filter(
            (User.email == payload.email) |
            (User.username == payload.username)
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        user = User(
            email=payload.email,
            username=payload.username,
            hashed_password=hash_password(payload.password)
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def login(db: Session, payload: UserLogin):

        user = db.query(User).filter(User.email == payload.email).first()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token(str(user.id))

        return token