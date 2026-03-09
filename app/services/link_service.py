import json
import secrets
import string
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.cache import redis_client
from app.core.config import settings
from app.db.models.archive import ArchiveLink
from app.db.models.link import Link
from app.db.models.user import User
from app.schemas.link import LinkCreate, LinkUpdate

ALPHABET = string.ascii_letters + string.digits


class LinkService:
    @staticmethod
    def _generate_short_code(length: int = 6) -> str:
        return "".join(secrets.choice(ALPHABET) for _ in range(length))

    @staticmethod
    def _cache_key(short_code: str) -> str:
        return "link:{0}".format(short_code)

    @staticmethod
    def _stats_cache_key(short_code: str) -> str:
        return "stats:{0}".format(short_code)

    @staticmethod
    def _clear_cache(short_code: str) -> None:
        redis_client.delete(LinkService._cache_key(short_code))
        redis_client.delete(LinkService._stats_cache_key(short_code))

    @staticmethod
    def create_link(
        db: Session,
        payload: LinkCreate,
        user: Optional[User] = None,
    ) -> Link:
        now = datetime.now(timezone.utc)

        if payload.expires_at is not None:
            expires_at = payload.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="expires_at must be in the future",
                )
        else:
            expires_at = None

        short_code = payload.custom_alias

        if short_code:
            existing_alias = db.query(Link).filter(Link.short_code == short_code).first()
            if existing_alias and existing_alias.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Alias already exists",
                )
        else:
            while True:
                candidate = LinkService._generate_short_code()
                existing_code = db.query(Link).filter(Link.short_code == candidate).first()
                if not existing_code:
                    short_code = candidate
                    break

        link = Link(
            original_url=str(payload.original_url),
            short_code=short_code,
            custom_alias=payload.custom_alias,
            user_id=user.id if user else None,
            expires_at=expires_at,
        )

        db.add(link)
        db.commit()
        db.refresh(link)

        redis_client.setex(
            LinkService._cache_key(link.short_code),
            settings.CACHE_TTL_SECONDS,
            json.dumps({
                "original_url": link.original_url,
                "expires_at": link.expires_at.isoformat() if link.expires_at else None,
                "is_active": link.is_active,
            }),
        )

        return link

    @staticmethod
    def get_redirect_link(db: Session, short_code: str) -> Link:
        cached = redis_client.get(LinkService._cache_key(short_code))
        link = None

        if cached:
            link = db.query(Link).filter(Link.short_code == short_code).first()

        if not link:
            link = db.query(Link).filter(
                Link.short_code == short_code,
                Link.is_active == True,
            ).first()

            if link:
                redis_client.setex(
                    LinkService._cache_key(short_code),
                    settings.CACHE_TTL_SECONDS,
                    json.dumps({
                        "original_url": link.original_url,
                        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
                        "is_active": link.is_active,
                    }),
                )

        if not link or not link.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found",
            )

        now = datetime.now(timezone.utc)

        if link.expires_at is not None:
            expires_at = link.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Link has expired",
                )

        link.click_count += 1
        link.last_accessed_at = now
        db.commit()
        db.refresh(link)

        redis_client.delete(LinkService._stats_cache_key(short_code))

        return link

    @staticmethod
    def get_stats(db: Session, short_code: str) -> Link:
        cached = redis_client.get(LinkService._stats_cache_key(short_code))
        if cached:
            data = json.loads(cached)
            link = db.query(Link).filter(Link.short_code == data["short_code"]).first()
            if link:
                return link

        link = db.query(Link).filter(Link.short_code == short_code).first()
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found",
            )

        redis_client.setex(
            LinkService._stats_cache_key(short_code),
            60,
            json.dumps({"short_code": short_code}),
        )

        return link

    @staticmethod
    def search_by_original_url(db: Session, original_url: str) -> List[Link]:
        return db.query(Link).filter(
            Link.original_url == original_url,
            Link.is_active == True,
        ).all()

    @staticmethod
    def update_link(
        db: Session,
        short_code: str,
        payload: LinkUpdate,
        current_user: User,
    ) -> Link:
        link = db.query(Link).filter(
            Link.short_code == short_code,
            Link.is_active == True,
        ).first()

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found",
            )

        if link.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )

        if payload.original_url is not None:
            link.original_url = str(payload.original_url)

        if payload.expires_at is not None:
            expires_at = payload.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="expires_at must be in the future",
                )

            link.expires_at = expires_at

        db.commit()
        db.refresh(link)

        LinkService._clear_cache(short_code)

        return link

    @staticmethod
    def delete_link(
        db: Session,
        short_code: str,
        current_user: User,
    ) -> None:
        link = db.query(Link).filter(
            Link.short_code == short_code,
            Link.is_active == True,
        ).first()

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found",
            )

        if link.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )

        archive = ArchiveLink(
            original_url=link.original_url,
            short_code=link.short_code,
            user_id=link.user_id,
            created_at=link.created_at,
            archived_at=datetime.now(timezone.utc),
            last_accessed_at=link.last_accessed_at,
            click_count=link.click_count,
            reason="manual_delete",
        )

        db.add(archive)

        link.is_active = False
        link.deleted_at = datetime.now(timezone.utc)

        db.commit()

        LinkService._clear_cache(short_code)