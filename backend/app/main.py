"""NIET AI-QPG FastAPI application entry point."""
from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import models  # noqa: F401 - registers all metadata
from .bootstrap import seed_database
from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import academic, admin, auth, documents, papers

settings = get_settings()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname, "logger": record.name, "message": record.getMessage(),
        })


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("niet_qpg")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    logger.info("application_started")
    yield
    logger.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Private syllabus-grounded question paper generation for NIET staff.",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_and_request_logging(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    logger.info(json.dumps({
        "event": "http_request", "method": request.method, "path": request.url.path,
        "status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }))
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]} for err in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Please correct the highlighted fields.", "errors": errors})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("unhandled_error path=%s", request.url.path)
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={"detail": "The service could not complete this request. Please try again or contact the administrator."})
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error"})


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(academic.router)
app.include_router(documents.router)
app.include_router(papers.router)


@app.get("/api/health", tags=["System"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "ai_provider": settings.ai_provider}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "unavailable"})


frontend = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
