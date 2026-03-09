from typing import Optional, List

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.security import decode_token
from app.db.models.user import User
from app.schemas.link import LinkCreate, LinkUpdate, LinkResponse, LinkSearchResponse
from app.schemas.stats import LinkStatsResponse
from app.services.link_service import LinkService

router = APIRouter(
    prefix="/api/links",
    tags=["links"]
)

@router.post("/shorten", response_model=LinkResponse)
def shorten_link(
    payload: LinkCreate,
    db: Session = Depends(get_db),
):
    link = LinkService.create_link(db, payload)

    return LinkResponse(
        original_url=link.original_url,
        short_code=link.short_code,
        short_url=f"{settings.BASE_URL}/{link.short_code}",
        created_at=link.created_at,
        expires_at=link.expires_at,
    )

@router.get("/{short_code}/stats", response_model=LinkStatsResponse)
def link_stats(
    short_code: str,
    db: Session = Depends(get_db),
):
    return LinkService.get_stats(db, short_code)

@router.get("/search", response_model=List[LinkSearchResponse])
def search_link(
    original_url: str = Query(...),
    db: Session = Depends(get_db),
):
    links = LinkService.search_by_original_url(db, original_url)

    return [
        LinkSearchResponse(
            original_url=l.original_url,
            short_code=l.short_code,
            short_url=f"{settings.BASE_URL}/{l.short_code}",
        )
        for l in links
    ]

@router.put("/{short_code}")
def update_link(
    short_code: str,
    payload: LinkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return LinkService.update_link(db, short_code, payload, current_user)

@router.delete("/{short_code}")
def delete_link(
    short_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    LinkService.delete_link(db, short_code, current_user)
    return {"message": "deleted"}