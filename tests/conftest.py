import os
from unittest.mock import MagicMock

# ── 1. Set all required env vars before importing any app module ──────────────
os.environ.setdefault("APP_NAME", "URLShortener-Test")
os.environ.setdefault("APP_HOST", "0.0.0.0")
os.environ.setdefault("APP_PORT", "8000")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("BASE_URL", "http://testserver")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_url_shortener.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("INACTIVE_DAYS", "90")
os.environ.setdefault("CACHE_TTL_SECONDS", "300")

# ── 2. Build redis mock and inject into cache module ─────────────────────────

mock_redis = MagicMock()
mock_redis.get.return_value = None
mock_redis.setex.return_value = True
mock_redis.delete.return_value = 1

import app.core.cache as _cache_mod  # noqa: E402
_cache_mod.redis_client = mock_redis


import app.services.link_service as _link_svc  # noqa: E402
_link_svc.redis_client = mock_redis

# ── 3. Safe to import the rest of the project ─────────────────────────────────
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402  — also triggers Base.metadata.create_all
from app.api.deps import get_db as deps_get_db  # noqa: E402
from app.api.auth import get_db as auth_get_db  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_redis():

    mock_redis.reset_mock()
    mock_redis.get.return_value = None
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = 1
    yield


@pytest.fixture()
def mock_redis_client():
    return mock_redis


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def _override():
        yield db

    app.dependency_overrides[deps_get_db] = _override
    app.dependency_overrides[auth_get_db] = _override

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest.fixture()
def registered_user(client):
    creds = {
        "email": "user@example.com",
        "username": "testuser",
        "password": "secret123",
    }
    r = client.post("/api/auth/register", json=creds)
    assert r.status_code == 200
    return creds


@pytest.fixture()
def auth_headers(client, registered_user):
    r = client.post("/api/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── Session-scoped cleanup ────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _cleanup_sqlite_file():
    yield
    import pathlib
    pathlib.Path("./test_url_shortener.db").unlink(missing_ok=True)
