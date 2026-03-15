import json
from datetime import datetime, timedelta, timezone

import pytest

from app.db.models.link import Link
from app.db.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _future_iso(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past_iso(hours: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _make_owned_link(db, user_email: str, short_code: str = "mylink",
                     original_url: str = "https://example.com/") -> Link:

    user = db.query(User).filter(User.email == user_email).first()
    link = Link(
        original_url=original_url,
        short_code=short_code,
        user_id=user.id,
        is_active=True,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ── Healthcheck ───────────────────────────────────────────────────────────────

class TestHealthcheck:
    def test_healthcheck_returns_ok(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── POST /api/links/shorten ───────────────────────────────────────────────────

class TestShortenLink:
    def test_shorten_success(self, client):
        r = client.post("/api/links/shorten", json={"original_url": "https://example.com/"})
        assert r.status_code == 200
        data = r.json()
        assert data["original_url"] == "https://example.com/"
        assert "short_code" in data
        assert "short_url" in data
        assert data["short_url"].endswith(data["short_code"])
        assert data["expires_at"] is None

    def test_shorten_with_custom_alias(self, client):
        r = client.post("/api/links/shorten", json={
            "original_url": "https://example.com/",
            "custom_alias": "myalias",
        })
        assert r.status_code == 200
        assert r.json()["short_code"] == "myalias"

    def test_shorten_with_future_expiry(self, client):
        r = client.post("/api/links/shorten", json={
            "original_url": "https://example.com/",
            "expires_at": _future_iso(48),
        })
        assert r.status_code == 200
        assert r.json()["expires_at"] is not None

    def test_shorten_with_past_expiry_returns_400(self, client):
        r = client.post("/api/links/shorten", json={
            "original_url": "https://example.com/",
            "expires_at": _past_iso(),
        })
        assert r.status_code == 400
        assert "future" in r.json()["detail"].lower()

    def test_shorten_duplicate_active_alias_returns_400(self, client):
        payload = {"original_url": "https://example.com/", "custom_alias": "taken"}
        client.post("/api/links/shorten", json=payload)
        r = client.post("/api/links/shorten", json=payload)
        assert r.status_code == 400
        assert "alias" in r.json()["detail"].lower()

    def test_shorten_invalid_url_returns_422(self, client):
        r = client.post("/api/links/shorten", json={"original_url": "not-a-url"})
        assert r.status_code == 422

    def test_shorten_alias_too_short_returns_422(self, client):
        r = client.post("/api/links/shorten", json={
            "original_url": "https://example.com/",
            "custom_alias": "ab",  # min 3
        })
        assert r.status_code == 422

    def test_shorten_alias_invalid_chars_returns_422(self, client):
        r = client.post("/api/links/shorten", json={
            "original_url": "https://example.com/",
            "custom_alias": "has space",
        })
        assert r.status_code == 422

    def test_shorten_caches_in_redis(self, client, mock_redis_client):
        client.post("/api/links/shorten", json={"original_url": "https://example.com/"})
        mock_redis_client.setex.assert_called_once()


# ── GET /api/links/{short_code}/stats ─────────────────────────────────────────

class TestLinkStats:
    def test_stats_success(self, client):
        create_r = client.post("/api/links/shorten", json={"original_url": "https://stats.example.com/"})
        short_code = create_r.json()["short_code"]

        r = client.get(f"/api/links/{short_code}/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["short_code"] == short_code
        assert data["click_count"] == 0
        assert "created_at" in data

    def test_stats_not_found_returns_404(self, client):
        r = client.get("/api/links/doesnotexist/stats")
        assert r.status_code == 404

    def test_stats_uses_cache_on_hit(self, client, db, mock_redis_client):

        link = Link(original_url="https://cached.example.com/", short_code="cachedstats", is_active=True)
        db.add(link)
        db.commit()

        # cache hit
        mock_redis_client.get.return_value = json.dumps({"short_code": "cachedstats"})

        r = client.get("/api/links/cachedstats/stats")
        assert r.status_code == 200
        assert r.json()["short_code"] == "cachedstats"


# ── GET /api/links/search ──────────────────────────────────────────────────────

class TestSearchLink:
    def test_search_returns_matching_links(self, client):
        url = "https://searchable.example.com/"
        client.post("/api/links/shorten", json={"original_url": url})
        client.post("/api/links/shorten", json={"original_url": url, "custom_alias": "alias2nd"})

        r = client.get(f"/api/links/search?original_url={url}")
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 2
        assert all(item["original_url"] == url for item in results)

    def test_search_returns_empty_list_when_no_match(self, client):
        r = client.get("/api/links/search?original_url=https://noone.example.com/")
        assert r.status_code == 200
        assert r.json() == []

    def test_search_missing_param_returns_422(self, client):
        r = client.get("/api/links/search")
        assert r.status_code == 422


# ── PUT /api/links/{short_code} ────────────────────────────────────────────────

class TestUpdateLink:
    def test_update_url_success(self, client, db, registered_user, auth_headers):
        link = _make_owned_link(db, registered_user["email"], "updateme")

        r = client.put("/api/links/updateme",
                       json={"original_url": "https://updated.example.com/"},
                       headers=auth_headers)
        assert r.status_code == 200

        db.expire_all()
        updated = db.query(Link).filter(Link.short_code == "updateme").first()
        assert updated.original_url == "https://updated.example.com/"

    def test_update_expiry_success(self, client, db, registered_user, auth_headers):
        link = _make_owned_link(db, registered_user["email"], "upexpiry")
        new_expiry = _future_iso(72)

        r = client.put("/api/links/upexpiry",
                       json={"expires_at": new_expiry},
                       headers=auth_headers)
        assert r.status_code == 200

    def test_update_past_expiry_returns_400(self, client, db, registered_user, auth_headers):
        _make_owned_link(db, registered_user["email"], "badexpiry")

        r = client.put("/api/links/badexpiry",
                       json={"expires_at": _past_iso()},
                       headers=auth_headers)
        assert r.status_code == 400

    def test_update_not_owner_returns_403(self, client, db, auth_headers):

        link = Link(original_url="https://example.com/", short_code="notmine", is_active=True)
        db.add(link)
        db.commit()

        r = client.put("/api/links/notmine",
                       json={"original_url": "https://evil.example.com/"},
                       headers=auth_headers)
        assert r.status_code == 403

    def test_update_unauthenticated_returns_401(self, client):
        r = client.put("/api/links/anything", json={"original_url": "https://x.com/"})
        assert r.status_code == 401

    def test_update_nonexistent_returns_404(self, client, auth_headers):
        r = client.put("/api/links/ghost",
                       json={"original_url": "https://x.com/"},
                       headers=auth_headers)
        assert r.status_code == 404

    def test_update_clears_cache(self, client, db, registered_user, auth_headers, mock_redis_client):
        _make_owned_link(db, registered_user["email"], "clearcache")

        client.put("/api/links/clearcache",
                   json={"original_url": "https://updated.example.com/"},
                   headers=auth_headers)

        assert mock_redis_client.delete.call_count == 2


# ── DELETE /api/links/{short_code} ────────────────────────────────────────────

class TestDeleteLink:
    def test_delete_success(self, client, db, registered_user, auth_headers):
        _make_owned_link(db, registered_user["email"], "todelete")

        r = client.delete("/api/links/todelete", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["message"] == "deleted"

        db.expire_all()
        link = db.query(Link).filter(Link.short_code == "todelete").first()
        assert link.is_active is False

    def test_delete_creates_archive_entry(self, client, db, registered_user, auth_headers):
        from app.db.models.archive import ArchiveLink

        _make_owned_link(db, registered_user["email"], "archiveme")

        client.delete("/api/links/archiveme", headers=auth_headers)

        db.expire_all()
        archive = db.query(ArchiveLink).filter(ArchiveLink.short_code == "archiveme").first()
        assert archive is not None
        assert archive.reason == "manual_delete"

    def test_delete_not_owner_returns_403(self, client, db, auth_headers):
        link = Link(original_url="https://example.com/", short_code="notmydel", is_active=True)
        db.add(link)
        db.commit()

        r = client.delete("/api/links/notmydel", headers=auth_headers)
        assert r.status_code == 403

    def test_delete_unauthenticated_returns_401(self, client):
        r = client.delete("/api/links/anything")
        assert r.status_code == 401

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        r = client.delete("/api/links/ghost", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_clears_cache(self, client, db, registered_user, auth_headers, mock_redis_client):
        _make_owned_link(db, registered_user["email"], "delcache")

        mock_redis_client.reset_mock()
        client.delete("/api/links/delcache", headers=auth_headers)
        assert mock_redis_client.delete.call_count == 2
