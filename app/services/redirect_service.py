from sqlalchemy.orm import Session

from app.db.models.link import Link
from app.services.link_service import LinkService


class RedirectService:
    @staticmethod
    def resolve_short_code(db: Session, short_code: str) -> Link:
        return LinkService.get_redirect_link(db, short_code)