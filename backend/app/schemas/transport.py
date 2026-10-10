from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class VehicleBase(BaseModel):
    registration_number: str
    capacity: int
    is_available: bool = True

class Vehicle(VehicleBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class RouteBase(BaseModel):
    name: str

class Route(RouteBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
