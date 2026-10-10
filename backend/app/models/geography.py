from sqlalchemy import Column, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class State(BaseModel):
    __tablename__ = "states"
    name = Column(String, index=True, nullable=False)
    code = Column(String, unique=True, index=True)
    districts = relationship("District", back_populates="state")

class District(BaseModel):
    __tablename__ = "districts"
    name = Column(String, index=True, nullable=False)
    state_id = Column(ForeignKey("states.id"), nullable=False)
    state = relationship("State", back_populates="districts")
    areas = relationship("Area", back_populates="district")

class Area(BaseModel):
    __tablename__ = "areas"
    name = Column(String, index=True, nullable=False)
    district_id = Column(ForeignKey("districts.id"), nullable=False)
    district = relationship("District", back_populates="areas")
    boundary = Column(String) # WKT String (fallback for SQLite)
    stops = relationship("BusStop", back_populates="area")

class BusStop(BaseModel):
    __tablename__ = "bus_stops"
    name = Column(String, index=True, nullable=False)
    area_id = Column(ForeignKey("areas.id"), nullable=False)
    area = relationship("Area", back_populates="stops")
    location = Column(String) # WKT String (fallback for SQLite)
    waiting_capacity = Column(Float)
