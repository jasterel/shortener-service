from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: Optional[str] = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_-]{3,32}$"
    )
    expires_at: Optional[datetime] = None


class LinkUpdate(BaseModel):
    original_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None


class LinkResponse(BaseModel):
    original_url: str
    short_code: str
    short_url: str
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class LinkSearchResponse(BaseModel):
    original_url: str
    short_code: str
    short_url: str