from datetime import datetime, timedelta, timezone

import pytest

from app.db.models.link import Link
from app.db.models.archive import ArchiveLink
from app.services.cleanup_service import CleanupService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _active_link(db, short_code: str, expires_at=None, last_accessed_at=None) -> Link:
    link = Link(
        original_url="https://example.com/",
        short_code=short_code,
        is_active=True,
        expires_at=expires_at,
        last_accessed_at=last_accessed_at,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ── remove_expired_links ──────────────────────────────────────────────────────

class TestRemoveExpiredLinks:
    def test_removes_expired_link(self, db):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        _active_link(db, "exp1", expires_at=past)

        count = CleanupService.remove_expired_links()

        assert count == 1
        db.expire_all()
        link = db.query(Link).filter(Link.short_code == "exp1").first()
        assert link.is_active is False

    def test_archives_expired_link(self, db):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        _active_link(db, "exp2", expires_at=past)

        CleanupService.remove_expired_links()

        db.expire_all()
        archive = db.query(ArchiveLink).filter(ArchiveLink.short_code == "exp2").first()
        assert archive is not None
        assert archive.reason == "expired"

    def test_skips_non_expired_links(self, db):
        future = datetime.now(timezone.utc) + timedelta(hours=24)
        _active_link(db, "notexp", expires_at=future)

        count = CleanupService.remove_expired_links()

        assert count == 0
        db.expire_all()
        link = db.query(Link).filter(Link.short_code == "notexp").first()
        assert link.is_active is True

    def test_skips_links_without_expiry(self, db):
        _active_link(db, "noexpiry")  # expires_at=None

        count = CleanupService.remove_expired_links()

        assert count == 0

    def test_returns_correct_count_for_multiple(self, db):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(hours=24)
        _active_link(db, "e1", expires_at=past)
        _active_link(db, "e2", expires_at=past)
        _active_link(db, "e3", expires_at=future)

        count = CleanupService.remove_expired_links()
        assert count == 2


# ── remove_inactive_links ─────────────────────────────────────────────────────

class TestRemoveInactiveLinks:
    def test_removes_inactive_link(self, db):
        old_access = datetime.now(timezone.utc) - timedelta(days=100)
        _active_link(db, "old1", last_accessed_at=old_access)

        count = CleanupService.remove_inactive_links()

        assert count == 1
        db.expire_all()
        link = db.query(Link).filter(Link.short_code == "old1").first()
        assert link.is_active is False

    def test_archives_inactive_link(self, db):
        old_access = datetime.now(timezone.utc) - timedelta(days=100)
        _active_link(db, "old2", last_accessed_at=old_access)

        CleanupService.remove_inactive_links()

        db.expire_all()
        archive = db.query(ArchiveLink).filter(ArchiveLink.short_code == "old2").first()
        assert archive is not None
        assert archive.reason == "inactive"

    def test_skips_recently_accessed_links(self, db):
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        _active_link(db, "recent1", last_accessed_at=recent)

        count = CleanupService.remove_inactive_links()
        assert count == 0

    def test_skips_never_accessed_links(self, db):

        _active_link(db, "neveraccessed")

        count = CleanupService.remove_inactive_links()
        assert count == 0
