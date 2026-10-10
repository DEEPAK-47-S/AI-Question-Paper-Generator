from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class ForecastRequest(BaseModel):
    area_id: UUID
    base_demand: int
    target_time: datetime
    has_event: bool = False

class ForecastResponse(BaseModel):
    area_id: UUID
    target_time: datetime
    predicted_demand: int
    model_used: str
