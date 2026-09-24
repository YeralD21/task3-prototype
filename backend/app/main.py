"""Punto de entrada de la API FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.atlas import router as atlas_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.health import router as health_router
from app.api.routes.playbook import router as playbook_router
from app.api.routes.radio import router as radio_router
from app.api.routes.search import router as search_router
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(datasets_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(atlas_router, prefix="/api/v1")
app.include_router(playbook_router, prefix="/api/v1")
app.include_router(radio_router, prefix="/api/v1")
