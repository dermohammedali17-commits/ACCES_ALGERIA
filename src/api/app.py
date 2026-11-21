from __future__ import annotations

from fastapi import FastAPI

from src.api.core.config import settings
from src.api.middleware.rate_limiter import LoginRateLimitMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.api.routers.auth import router as auth_router
from src.api.routers.lpsme import router as lpsme_router
from src.api.routers.workspaces import router as workspaces_router

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
# Security Middleware
app.add_middleware(
    LoginRateLimitMiddleware,
    settings=settings,
)
app.add_middleware(
    SecurityHeadersMiddleware,
    settings=settings,
)
# API Routers
app.include_router(
    lpsme_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    auth_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    workspaces_router,
    prefix=settings.api_v1_prefix,
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
    }