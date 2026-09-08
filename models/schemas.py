from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class UbicacionGeografica(BaseModel):
    ciudad: str | None = None
    pais: str | None = None


class _CasoFraudeBase(BaseModel):
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


class CasoExtraido(_CasoFraudeBase):
    pass


class CasoA1(_CasoFraudeBase):
    pass


class IndicadoresPatron(BaseModel):
    total_casos: int
    casos_por_modus_operandi: dict[str, int]
    casos_por_canal: dict[str, int]
    casos_por_categoria_comercio: dict[str, int]
    casos_por_comercio: dict[str, int]
    casos_por_rango_monto: dict[str, int]
    monto_promedio: float | None = None
    monto_mediana: float | None = None
    monto_minimo: float | None = None
    monto_maximo: float | None = None


class HipotesisPatron(BaseModel):
    pattern_id: str
    hypothesis: str
    indicators: dict[str, str | list[str] | int | float | None]
    confidence: float = Field(ge=0.0, le=1.0)


class ResultadoA2(BaseModel):
    analysis_id: str
    timestamp: datetime
    cases_analyzed: int
    indicators: IndicadoresPatron
    patterns: list[HipotesisPatron]