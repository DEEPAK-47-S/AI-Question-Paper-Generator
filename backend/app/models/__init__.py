from app.models.base import Base, BaseModel
from app.models.geography import State, District, Area, BusStop
from app.models.transport import Vehicle, Route, RouteStop, ScheduledTrip
from app.models.population import PopulationEstimate, CrowdObservation
from app.models.events import Event, WeatherForecast
from app.models.facilities import Facility

# This file ensures all models are imported and metadata is registered for Alembic
__all__ = [
    "Base", "BaseModel",
    "State", "District", "Area", "BusStop",
    "Vehicle", "Route", "RouteStop", "ScheduledTrip",
    "PopulationEstimate", "CrowdObservation",
    "Event", "WeatherForecast",
    "Facility"
]
