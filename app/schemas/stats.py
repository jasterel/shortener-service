from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LinkStatsResponse(BaseModel):
    original_url: str
    short_code: str
    created_at: datetime
    click_count: int
    last_accessed_at: Optional[datetime]
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True