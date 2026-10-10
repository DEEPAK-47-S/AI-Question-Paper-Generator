from fastapi import APIRouter
from app.schemas.optimization import OptimizationRequest, OptimizationResponse, StopAllocation
from app.services.optimization.engine import optimization_engine, ORTOOLS_AVAILABLE

router = APIRouter()

@router.post("/run", response_model=OptimizationResponse)
async def run_optimization(request: OptimizationRequest):
    allocations = optimization_engine.optimize_fleet(
        available_buses=request.available_buses,
        demand_by_stop=request.demand_by_stop,
        bus_capacity=request.bus_capacity
    )
    
    result = []
    total_unmet = 0
    for stop_id, allocated in allocations.items():
        demand = request.demand_by_stop.get(stop_id, 0)
        capacity_provided = allocated * request.bus_capacity
        fulfilled = min(demand, capacity_provided)
        unmet = max(0, demand - capacity_provided)
        total_unmet += unmet
        
        result.append(StopAllocation(
            stop_id=stop_id,
            allocated_buses=allocated,
            fulfilled_demand=fulfilled,
            unmet_demand=unmet
        ))
        
    return OptimizationResponse(
        allocations=result,
        total_unmet_demand=total_unmet,
        engine_used="Google OR-Tools" if ORTOOLS_AVAILABLE else "Greedy Fallback"
    )
