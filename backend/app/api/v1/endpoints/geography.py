from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.api.deps import get_db
from app.models.geography import State, District, Area, BusStop
from app.schemas.geography import State as StateSchema, District as DistrictSchema, Area as AreaSchema, BusStop as BusStopSchema

router = APIRouter()

@router.get("/states", response_model=List[StateSchema])
async def get_states(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(State))
    return result.scalars().all()

@router.get("/districts", response_model=List[DistrictSchema])
async def get_districts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(District))
    return result.scalars().all()

@router.get("/areas", response_model=List[AreaSchema])
async def get_areas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Area))
    return result.scalars().all()

@router.get("/stops", response_model=List[BusStopSchema])
async def get_stops(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BusStop))
    return result.scalars().all()
