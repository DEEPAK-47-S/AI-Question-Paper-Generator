from pydantic import BaseModel
from typing import Dict

class OptimizationRequest(BaseModel):
    available_buses: int
    demand_by_stop: Dict[str, int]
    bus_capacity: int = 50

class StopAllocation(BaseModel):
    stop_id: str
    allocated_buses: int
    fulfilled_demand: int
    unmet_demand: int

class OptimizationResponse(BaseModel):
    allocations: list[StopAllocation]
    total_unmet_demand: int
    engine_used: str
