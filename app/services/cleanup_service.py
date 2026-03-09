from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.db.models.link import Link
from app.db.models.archive import ArchiveLink
from app.db.session import SessionLocal
from app.core.config import settings


class CleanupService:

    @staticmethod
    def remove_expired_links():
        db: Session = SessionLocal()

        now = datetime.now(timezone.utc)

        links = db.query(Link).filter(
            Link.expires_at != None,
            Link.expires_at <= now,
            Link.is_active == True
        ).all()

        for link in links:

            archive = ArchiveLink(
                original_url=link.original_url,
                short_code=link.short_code,
                user_id=link.user_id,
                created_at=link.created_at,
                archived_at=now,
                last_accessed_at=link.last_accessed_at,
                click_count=link.click_count,
                reason="expired"
            )

            db.add(archive)

            link.is_active = False
            link.deleted_at = now

        db.commit()
        db.close()

        return len(links)

    @staticmethod
    def remove_inactive_links():
        db: Session = SessionLocal()

        threshold = datetime.now(timezone.utc) - timedelta(days=settings.INACTIVE_DAYS)

        links = db.query(Link).filter(
            Link.last_accessed_at != None,
            Link.last_accessed_at < threshold,
            Link.is_active == True
        ).all()

        for link in links:

            archive = ArchiveLink(
                original_url=link.original_url,
                short_code=link.short_code,
                user_id=link.user_id,
                created_at=link.created_at,
                archived_at=datetime.now(timezone.utc),
                last_accessed_at=link.last_accessed_at,
                click_count=link.click_count,
                reason="inactive"
            )

            db.add(archive)

            link.is_active = False
            link.deleted_at = datetime.now(timezone.utc)

        db.commit()
        db.close()

        return len(links)