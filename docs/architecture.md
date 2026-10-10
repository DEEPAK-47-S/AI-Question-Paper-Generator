# AI-Powered Government Resource Planning Platform

## Architecture Overview

The platform is designed as a modern, decoupled web application consisting of a React-based single-page application (SPA) frontend and a Python FastAPI backend. The system uses a PostgreSQL database with PostGIS extensions for geospatial data handling.

### Technology Stack

#### Frontend
- **Framework:** React 18+ with TypeScript
- **Build Tool:** Vite
- **Styling:** Tailwind CSS + shadcn/ui for components
- **State Management:** React Query (TanStack Query) for server state
- **Routing:** React Router DOM
- **Forms:** React Hook Form + Zod for validation
- **Visualization:** Recharts (charts), Leaflet (maps)

#### Backend
- **Framework:** FastAPI (Python 3.10+)
- **Data Validation:** Pydantic
- **ORM:** SQLAlchemy 2.x
- **Migrations:** Alembic
- **AI/ML:** Scikit-learn, Pandas, NumPy
- **Optimization:** Google OR-Tools

#### Database
- **Primary Datastore:** PostgreSQL 15+
- **Geospatial Extension:** PostGIS 3+

#### Infrastructure & DevOps
- **Containerization:** Docker & Docker Compose
- **Testing:** Pytest (Backend), Vitest/React Testing Library (Frontend), Playwright (E2E)

### System Components

1. **Frontend Application:** Handles user interactions, data visualization, and map rendering. Communicates with the backend via REST API.
2. **Backend API:** Exposes RESTful endpoints under `/api/v1`. Handles business logic, data access, authentication, and authorization.
3. **Database:** Stores all persistent data including geographic entities, population estimates, transportation schedules, user accounts, and optimization histories.
4. **Forecasting Engine:** Python module integrated with the backend that uses scikit-learn for predicting future crowd and resource demand.
5. **Optimization Engine:** Python module using Google OR-Tools to calculate the most efficient allocation of constrained resources (e.g., fixed bus fleet) while respecting operational constraints.

### Data Flow

1. **Ingestion:** Data providers (or file uploads) submit historical population, event, and transport data to the backend API.
2. **Storage:** Backend validates and stores data in PostgreSQL/PostGIS.
3. **Analysis & Prediction:** The forecasting engine processes historical data, weather, and event schedules to predict future demand.
4. **Optimization:** Based on forecast demand and current resource availability, the optimization engine generates allocation recommendations.
5. **Presentation:** The frontend fetches and visualizes actuals, forecasts, and recommendations. Users can review, approve, or reject recommendations.

### Modules

1. **Auth & Roles:** Manages access control (e.g., Administrator, District Planner).
2. **Geography:** Manages spatial hierarchy (Country -> State -> District -> Area -> Stop/Facility).
3. **Population & Observations:** Manages resident population and crowd density estimates.
4. **Events & Weather:** Manages schedules that impact demand.
5. **Transport & Fleet:** Manages vehicles, stops, routes, and capacities.
6. **Facilities:** Manages non-transport public resources.
7. **Forecasting:** Generates time-series predictions.
8. **Optimization:** Generates and evaluates resource re-allocation scenarios.
9. **Reports:** Generates summaries and exports.

### API Contracts

All APIs will follow RESTful principles and return JSON. Standard error formats will be used for validation and authorization failures.

Example endpoints:
- `GET /api/v1/geography/districts`
- `GET /api/v1/transport/stops`
- `POST /api/v1/forecasts/run`
- `POST /api/v1/allocations/optimize`

### Unavailable Integrations & Fallbacks
- Real-time live passenger counting APIs: Fallback to simulated synthetic historical and real-time data generators.
- Live weather APIs: Fallback to seeded weather forecast tables.
- Hardware sensor integrations: Fallback to manual CSV ingestion or internal API endpoints.
