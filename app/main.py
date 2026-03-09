from fastapi import FastAPI

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

from app.db.models import User, Link, ArchiveLink  # noqa: F401

from app.api.auth import router as auth_router
from app.api.links import router as links_router
from app.api.redirect import router as redirect_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

app.include_router(auth_router)
app.include_router(links_router)
app.include_router(redirect_router)

@app.get("/")
def healthcheck():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
    }