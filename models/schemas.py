from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UbicacionGeografica(BaseModel):
    ciudad: str | None = None
    pais: str | None = None


class CasoExtraido(BaseModel):
    case_id: str
    timestamp: datetime
    transcript_text: str
    monto_reportado: float | None = None
    moneda: str | None = None
    comercio_nombre: str | None = None
    comercio_categoria: str | None = None
    modus_operandi: str | None = None
    canal_fraude: str | None = None
    ubicacion_geografica: UbicacionGeografica = Field(default_factory=UbicacionGeografica)
    nivel_confianza_extraccion: float = Field(ge=0.0, le=1.0)
