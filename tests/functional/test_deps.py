from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token


# ── get_db generators ─────────────────────────────────────────────────────────

class TestGetDb:
    def test_deps_get_db_yields_a_session(self):

        from app.api.deps import get_db
        gen = get_db()
        session = next(gen)
        assert session is not None
        try:
            next(gen)
        except StopIteration:
            pass

    def test_auth_get_db_yields_a_session(self):

        from app.api.auth import get_db
        gen = get_db()
        session = next(gen)
        assert session is not None
        try:
            next(gen)
        except StopIteration:
            pass


# ── get_current_user error paths ──────────────────────────────────────────────

class TestGetCurrentUser:
    def test_invalid_token_returns_401(self, client, db):

        r = client.put(
            "/api/links/anything",
            json={"original_url": "https://x.com/"},
            headers={"Authorization": "Bearer this.is.garbage"},
        )
        assert r.status_code == 401

    def test_token_without_sub_returns_401(self, client, db):

        token_no_sub = jwt.encode(
            {"exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        r = client.put(
            "/api/links/anything",
            json={"original_url": "https://x.com/"},
            headers={"Authorization": f"Bearer {token_no_sub}"},
        )
        assert r.status_code == 401

    def test_token_for_nonexistent_user_returns_401(self, client, db):

        token = create_access_token("999999")  # no such user in test DB
        r = client.put(
            "/api/links/anything",
            json={"original_url": "https://x.com/"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401
