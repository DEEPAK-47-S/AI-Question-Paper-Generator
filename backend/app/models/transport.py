from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Vehicle(BaseModel):
    __tablename__ = "vehicles"
    registration_number = Column(String, unique=True, index=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    is_available = Column(Boolean, default=True)

class Route(BaseModel):
    __tablename__ = "routes"
    name = Column(String, index=True, nullable=False)

class RouteStop(BaseModel):
    __tablename__ = "route_stops"
    route_id = Column(ForeignKey("routes.id"), nullable=False)
    stop_id = Column(ForeignKey("bus_stops.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    estimated_travel_time_mins = Column(Float) # from previous stop

class ScheduledTrip(BaseModel):
    __tablename__ = "scheduled_trips"
    route_id = Column(ForeignKey("routes.id"), nullable=False)
    vehicle_id = Column(ForeignKey("vehicles.id")) # Can be assigned later
    departure_time = Column(DateTime(timezone=True), nullable=False)
    is_essential = Column(Boolean, default=False)
