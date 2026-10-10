from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.api.deps import get_db
from app.models.facilities import Facility
from app.schemas.facilities import Facility as FacilitySchema

router = APIRouter()

@router.get("/", response_model=List[FacilitySchema])
async def get_facilities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Facility))
    return result.scalars().all()
