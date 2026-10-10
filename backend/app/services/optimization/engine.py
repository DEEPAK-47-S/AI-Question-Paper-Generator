from typing import List, Dict, Tuple

try:
    from ortools.linear_solver import pywraplp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

class OptimizationEngine:
    def optimize_fleet(
        self, 
        available_buses: int, 
        demand_by_stop: Dict[str, int], 
        bus_capacity: int = 50
    ) -> Dict[str, int]:
        """
        Allocate a fixed number of buses to stops to minimize unmet demand.
        Returns a dict mapping stop_id to allocated_buses.
        """
        if ORTOOLS_AVAILABLE:
            return self._optimize_ortools(available_buses, demand_by_stop, bus_capacity)
        else:
            return self._optimize_greedy_fallback(available_buses, demand_by_stop, bus_capacity)

    def _optimize_ortools(self, available_buses: int, demand_by_stop: Dict[str, int], bus_capacity: int):
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            return self._optimize_greedy_fallback(available_buses, demand_by_stop, bus_capacity)

        stop_ids = list(demand_by_stop.keys())
        
        # Variables: number of buses allocated to each stop (integer)
        x = {}
        for stop in stop_ids:
            # Max buses a stop could possibly need to meet demand exactly
            max_needed = (demand_by_stop[stop] // bus_capacity) + 1
            x[stop] = solver.IntVar(0, max_needed, f'buses_{stop}')

        # Constraint: total buses allocated <= available_buses
        solver.Add(sum(x[stop] for stop in stop_ids) <= available_buses)

        # Objective: minimize unmet demand. 
        # Unmet demand for a stop = demand - (buses * capacity), lower bounded by 0.
        # Since we use a linear solver, we can maximize fulfilled demand instead.
        # Fulfilled demand = min(demand, buses * capacity).
        # We introduce a variable y[stop] for fulfilled demand.
        y = {}
        for stop in stop_ids:
            y[stop] = solver.IntVar(0, demand_by_stop[stop], f'fulfilled_{stop}')
            solver.Add(y[stop] <= x[stop] * bus_capacity)
            solver.Add(y[stop] <= demand_by_stop[stop])

        solver.Maximize(sum(y[stop] for stop in stop_ids))

        status = solver.Solve()

        allocation = {}
        if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
            for stop in stop_ids:
                allocation[stop] = int(x[stop].solution_value())
        else:
            # If solver fails, fallback
            allocation = self._optimize_greedy_fallback(available_buses, demand_by_stop, bus_capacity)

        return allocation

    def _optimize_greedy_fallback(self, available_buses: int, demand_by_stop: Dict[str, int], bus_capacity: int):
        # Fallback greedy allocation: assign bus to the stop with the highest unmet demand
        allocation = {stop: 0 for stop in demand_by_stop.keys()}
        unmet_demand = {stop: demand for stop, demand in demand_by_stop.items()}
        
        buses_left = available_buses
        while buses_left > 0 and sum(unmet_demand.values()) > 0:
            # Find stop with max unmet demand
            max_stop = max(unmet_demand, key=unmet_demand.get)
            allocation[max_stop] += 1
            buses_left -= 1
            unmet_demand[max_stop] = max(0, unmet_demand[max_stop] - bus_capacity)
            
        return allocation

optimization_engine = OptimizationEngine()
