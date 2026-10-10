from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from app.models.base import BaseModel

class Event(BaseModel):
    __tablename__ = "events"
    name = Column(String, index=True, nullable=False)
    area_id = Column(ForeignKey("areas.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    expected_attendance = Column(Integer)
    programme_details = Column(Text)

class WeatherForecast(BaseModel):
    __tablename__ = "weather_forecasts"
    area_id = Column(ForeignKey("areas.id"), nullable=False)
    forecast_time = Column(DateTime(timezone=True), nullable=False)
    temperature = Column(Integer)
    precipitation_chance = Column(Integer)
    condition = Column(String)
