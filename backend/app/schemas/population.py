from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class PopulationEstimateBase(BaseModel):
    area_id: UUID
    resident_count: int
    reference_date: datetime
    source: Optional[str] = None

class PopulationEstimate(PopulationEstimateBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class CrowdObservationBase(BaseModel):
    stop_id: UUID
    timestamp: datetime
    passenger_count: int
    source: Optional[str] = None

class CrowdObservation(CrowdObservationBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
