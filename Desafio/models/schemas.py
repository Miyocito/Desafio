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


class HipotesisA2(BaseModel):
    pattern_id: str
    hypothesis: str
    indicators: dict[str, str | list[str] | int | float | None]
    confidence: float = Field(ge=0.0, le=1.0)


class HipotesisPatron(HipotesisA2):
    pass


class ResultadoA2(BaseModel):
    analysis_id: str
    timestamp: datetime
    cases_analyzed: int
    indicators: IndicadoresPatron
    patterns: list[HipotesisPatron]


class TransaccionHistorica(BaseModel):
    transaction_id: str
    timestamp: datetime
    monto: float
    moneda: str | None = None
    comercio_nombre: str | None = None
    comercio_categoria: str | None = None
    canal: str | None = None
    ciudad: str | None = None
    pais: str | None = None
    modus_operandi: str | None = None
    fraude_confirmado: bool = False


class ResultadoValidacion(BaseModel):
    pattern_id: str
    hypothesis: str
    indicators: dict[str, str | list[str] | int | float | None]
    validated: bool
    transactions_analyzed: int
    matching_transactions: int
    recurrence_rate: float = Field(ge=0.0, le=1.0)
    transaction_volume: float = Field(ge=0.0)
    estimated_financial_cost: float = Field(ge=0.0)
    validation_reason: str


class ResultadoA3(BaseModel):
    analysis_id: str
    timestamp: datetime
    patterns_validated: int
    results: list[ResultadoValidacion]


class ReglaCondicion(BaseModel):
    field: str
    operator: str
    value: str | int | float | bool | list[str] | None


class ReglaAccion(BaseModel):
    type: str
    risk_level: str


class ReglaFraude(BaseModel):
    rule_id: str
    name: str
    description: str
    source_pattern_id: str
    conditions: list[ReglaCondicion]
    logic: str = "AND"
    action: ReglaAccion


class ResultadoA4(BaseModel):
    generation_id: str
    timestamp: datetime
    rules_generated: int
    rules: list[ReglaFraude]


class ResultadoBacktesting(BaseModel):
    rule_id: str
    rule_name: str
    transactions_analyzed: int
    transactions_detected: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    detection_rate: float = Field(ge=0.0, le=1.0)
    false_positive_rate: float = Field(ge=0.0, le=1.0)
    impact_avoided: float = Field(ge=0.0)
    certified: bool
    certification_reason: str


class ResultadoA5(BaseModel):
    certification_id: str
    timestamp: datetime
    rules_tested: int
    rules_certified: int
    results: list[ResultadoBacktesting]
