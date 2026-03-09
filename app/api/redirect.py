from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.redirect_service import RedirectService

router = APIRouter(tags=["redirect"])


@router.get("/{short_code}")
def redirect_to_original(
    short_code: str,
    db: Session = Depends(get_db),
):
    link = RedirectService.resolve_short_code(db, short_code)
    return RedirectResponse(url=link.original_url, status_code=307)