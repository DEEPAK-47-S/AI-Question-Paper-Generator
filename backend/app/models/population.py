from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from app.models.base import BaseModel

class PopulationEstimate(BaseModel):
    __tablename__ = "population_estimates"
    area_id = Column(ForeignKey("areas.id"), nullable=False)
    resident_count = Column(Integer, nullable=False)
    reference_date = Column(DateTime(timezone=True), nullable=False)
    source = Column(String)

class CrowdObservation(BaseModel):
    __tablename__ = "crowd_observations"
    stop_id = Column(ForeignKey("bus_stops.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    passenger_count = Column(Integer, nullable=False)
    source = Column(String) # e.g. "synthetic_sensor", "manual"
