"""Esquemas del endpoint de salud."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Respuesta pública del estado del servicio."""

    status: Literal["ok"]
    project: Literal["task3-prototype"]
