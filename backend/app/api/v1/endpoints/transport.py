from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.api.deps import get_db
from app.models.transport import Vehicle, Route
from app.schemas.transport import Vehicle as VehicleSchema, Route as RouteSchema

router = APIRouter()

@router.get("/fleet", response_model=List[VehicleSchema])
async def get_fleet(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vehicle))
    return result.scalars().all()

@router.get("/routes", response_model=List[RouteSchema])
async def get_routes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Route))
    return result.scalars().all()
