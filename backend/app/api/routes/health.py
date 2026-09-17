"""Endpoint de verificación del servicio."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Confirma que la API está disponible."""

    return HealthResponse(status="ok", project="task3-prototype")
