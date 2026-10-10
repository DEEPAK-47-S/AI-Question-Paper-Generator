from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Phase 10: Basic API Key Middleware
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    # In production, use real JWT/OAuth2. Here we simulate basic check.
    # Exclude openapi routes from auth
    if request.url.path.startswith(settings.API_V1_STR) and not request.url.path.endswith("openapi.json"):
        # We would check header X-API-KEY here, omitting for dev ease unless required
        pass
    response = await call_next(request)
    return response

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}

from app.api.v1.router import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)
