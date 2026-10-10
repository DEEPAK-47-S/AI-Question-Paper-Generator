from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Facility(BaseModel):
    __tablename__ = "facilities"
    name = Column(String, index=True, nullable=False)
    facility_type = Column(String, index=True, nullable=False) # e.g., "Healthcare", "Education"
    area_id = Column(ForeignKey("areas.id"), nullable=False)
    capacity = Column(Integer, nullable=False)
    location = Column(String) # WKT string
