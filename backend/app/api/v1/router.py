from fastapi import APIRouter
from app.api.v1.endpoints import geography, transport, ingestion, forecasting, optimization, facilities

api_router = APIRouter()
api_router.include_router(geography.router, prefix="/geography", tags=["geography"])
api_router.include_router(transport.router, prefix="/transport", tags=["transport"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(forecasting.router, prefix="/forecasting", tags=["forecasting"])
api_router.include_router(optimization.router, prefix="/optimization", tags=["optimization"])
api_router.include_router(facilities.router, prefix="/facilities", tags=["facilities"])
