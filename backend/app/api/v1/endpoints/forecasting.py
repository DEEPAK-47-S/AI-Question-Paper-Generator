from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.forecasting import ForecastRequest, ForecastResponse
from app.services.forecasting.engine import forecast_engine, SKLEARN_AVAILABLE

router = APIRouter()

@router.post("/run", response_model=ForecastResponse)
async def run_forecast(
    request: ForecastRequest,
    db: AsyncSession = Depends(get_db)
):
    prediction = forecast_engine.predict_demand(
        base_demand=request.base_demand,
        timestamp=request.target_time,
        has_event=request.has_event
    )
    
    return ForecastResponse(
        area_id=request.area_id,
        target_time=request.target_time,
        predicted_demand=prediction,
        model_used="RandomForestRegressor" if SKLEARN_AVAILABLE else "RuleBasedFallback"
    )
