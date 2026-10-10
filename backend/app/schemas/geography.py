from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional, List

class StateBase(BaseModel):
    name: str
    code: str

class State(StateBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class DistrictBase(BaseModel):
    name: str
    state_id: UUID

class District(DistrictBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class AreaBase(BaseModel):
    name: str
    district_id: UUID
    boundary: Optional[str] = None

class Area(AreaBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class BusStopBase(BaseModel):
    name: str
    area_id: UUID
    location: Optional[str] = None
    waiting_capacity: Optional[float] = None

class BusStop(BusStopBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
