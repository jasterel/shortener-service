from datetime import datetime, timedelta, timezone

import pytest

from app.db.models.link import Link


# ── Helpers ───────────────────────────────────────────────────────────────────

def _insert_link(db, short_code: str, original_url: str = "https://target.example.com/",
                 is_active: bool = True, expires_at=None) -> Link:
    link = Link(
        original_url=original_url,
        short_code=short_code,
        is_active=is_active,
        expires_at=expires_at,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRedirect:
    def test_redirect_returns_307(self, client, db):
        _insert_link(db, "abc123")
        r = client.get("/abc123", follow_redirects=False)
        assert r.status_code == 307

    def test_redirect_location_matches_original_url(self, client, db):
        original = "https://target.example.com/"
        _insert_link(db, "goto", original_url=original)
        r = client.get("/goto", follow_redirects=False)
        assert r.headers["location"] == original

    def test_redirect_nonexistent_code_returns_404(self, client):
        r = client.get("/doesnotexist", follow_redirects=False)
        assert r.status_code == 404

    def test_redirect_increments_click_count(self, client, db):
        link = _insert_link(db, "clickme")
        assert link.click_count == 0

        client.get("/clickme", follow_redirects=False)
        client.get("/clickme", follow_redirects=False)

        db.expire_all()
        updated = db.query(Link).filter(Link.short_code == "clickme").first()
        assert updated.click_count == 2

    def test_redirect_sets_last_accessed_at(self, client, db):
        _insert_link(db, "accessed")
        client.get("/accessed", follow_redirects=False)

        db.expire_all()
        link = db.query(Link).filter(Link.short_code == "accessed").first()
        assert link.last_accessed_at is not None

    def test_redirect_expired_link_returns_410(self, client, db):

        past = datetime.now(timezone.utc) - timedelta(hours=2)
        _insert_link(db, "expired", expires_at=past)

        r = client.get("/expired", follow_redirects=False)
        assert r.status_code == 410
        assert "expired" in r.json()["detail"].lower()

    def test_redirect_inactive_link_returns_404(self, client, db):

        _insert_link(db, "inactive", is_active=False)
        r = client.get("/inactive", follow_redirects=False)
        assert r.status_code == 404

    def test_redirect_with_cached_redis_hit(self, client, db, mock_redis_client):

        link = _insert_link(db, "cached")

        mock_redis_client.get.return_value = '{"original_url": "https://target.example.com/", "expires_at": null, "is_active": true}'

        r = client.get("/cached", follow_redirects=False)
        assert r.status_code == 307
