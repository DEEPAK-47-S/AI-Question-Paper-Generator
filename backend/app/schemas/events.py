from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class EventBase(BaseModel):
    name: str
    area_id: UUID
    start_time: datetime
    end_time: datetime
    expected_attendance: Optional[int] = None
    programme_details: Optional[str] = None

class Event(EventBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
