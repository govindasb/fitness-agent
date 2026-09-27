from datetime import datetime

from pydantic import BaseModel


class ParsedEvent(BaseModel):
    event_type: str
    raw_text: str
    event_time: datetime | None = None