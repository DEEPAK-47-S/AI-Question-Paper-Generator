from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional

class FacilityBase(BaseModel):
    name: str
    facility_type: str
    area_id: UUID
    capacity: int
    location: Optional[str] = None

class Facility(FacilityBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
