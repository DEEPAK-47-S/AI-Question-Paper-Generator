# AI-Powered Government Resource Planning Platform

This is a comprehensive, full-stack application designed to forecast crowd demand and optimize the allocation of government resources (such as transport fleets) using AI and constrained optimization techniques.

## Project Structure

- `frontend/`: React SPA built with Vite, TypeScript, Tailwind CSS, and shadcn/ui.
- `backend/`: Python API built with FastAPI, SQLAlchemy, and OR-Tools.
- `docs/`: Architecture and implementation checklist.

## Prerequisites

- Node.js (v18+)
- Python (3.10+)
- Docker & Docker Compose

## Quick Start (Development)

### 1. Start the Database
```bash
docker-compose up -d
```
This starts a PostgreSQL instance with the PostGIS extension on port 5432.

### 2. Run Backend
```bash
cd backend
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On Unix
# source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Run Frontend
```bash
cd frontend
npm install
npm run dev
```

## Documentation
- [Architecture](docs/architecture.md)
- [Checklist](docs/checklist.md)
