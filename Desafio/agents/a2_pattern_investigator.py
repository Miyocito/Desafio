from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime
from statistics import mean, median
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from models.schemas import CasoA1, HipotesisPatron, IndicadoresPatron, ResultadoA2


load_dotenv()


class _RespuestaLLMA2(BaseModel):
    patterns: list[HipotesisPatron] = Field(default_factory=list)


class A2PatternInvestigator:
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "Falta GEMINI_API_KEY en las variables de entorno. Define la clave en .env o en el entorno del sistema."
            )

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        self._llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.0,
        )

        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
Eres un investigador de patrones de fraude bancario.

Tu tarea es analizar indicadores previamente calculados por Python y formular hipótesis sobre posibles patrones de fraude.

Reglas obligatorias:
- No inventes información.
- No inventes casos.
- No inventes estadísticas.
- No modifiques los valores calculados por Python.
- No afirmes que un patrón es fraude confirmado.
- No consultes información externa.
- No realices cálculos estadísticos por tu cuenta.
- Si no existe evidencia suficiente, devuelve una lista vacía de patrones.
- La salida debe ser exclusivamente JSON estructurado.
- No incluyas explicaciones fuera del JSON.
- Usa español.

Esquema esperado:
{{
  "patterns": [
    {{
      "pattern_id": "string",
      "hypothesis": "string",
      "indicators": {{
        "modus_operandi": ["string"],
        "canal": ["string"],
        "categoria_comercio": ["string"],
        "comercio": ["string"],
        "rango_monto": ["string"],
        "cases": number
      }},
      "confidence": number
    }}
  ]
}}
                    """.strip(),
                ),
                (
                    "human",
                    """
Indicadores calculados por Python:
{indicators}

Concentraciones detectadas por Python:
{concentrations}

Instrucciones:
- Formula hipótesis únicamente con base en estos indicadores.
- Si no hay evidencia suficiente, devuelve {{"patterns": []}}.
- Devuelve solo JSON.
                    """.strip(),
                ),
            ]
        )

        self._chain = self._prompt | self._llm.with_structured_output(_RespuestaLLMA2)

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @staticmethod
    def _normalize_key(value: str | None) -> str | None:
        normalized = A2PatternInvestigator._normalize_text(value)
        if normalized is None:
            return None
        return re.sub(r"\s+", " ", normalized).lower()

    @staticmethod
    def _bucket_amount(amount: float | None) -> str | None:
        if amount is None:
            return None

        if amount < 50_000:
            return "0-49999"
        if amount < 200_000:
            return "50000-199999"
        if amount < 500_000:
            return "200000-499999"
        if amount < 1_000_000:
            return "500000-999999"
        return "1000000+"

    def _validate_cases(self, cases: list[CasoA1]) -> list[CasoA1]:
        validated_cases: list[CasoA1] = []
        for index, case in enumerate(cases, start=1):
            try:
                if isinstance(case, CasoA1):
                    validated = CasoA1.model_validate(case.model_dump())
                else:
                    validated = CasoA1.model_validate(case)
            except Exception as exc:
                raise ValueError(f"El caso en la posición {index} no cumple el esquema CasoA1: {exc}") from exc
            validated_cases.append(validated)
        return validated_cases

    def _calculate_indicators(self, cases: list[CasoA1]) -> tuple[IndicadoresPatron, list[dict[str, object]]]:
        modus_counter: Counter[str] = Counter()
        canal_counter: Counter[str] = Counter()
        categoria_counter: Counter[str] = Counter()
        comercio_counter: Counter[str] = Counter()
        rango_monto_counter: Counter[str] = Counter()

        monto_values: list[float] = []
        normalized_rows: list[dict[str, object]] = []

        for case in cases:
            modus = self._normalize_key(case.modus_operandi)
            canal = self._normalize_key(case.canal_fraude)
            categoria = self._normalize_key(case.comercio_categoria)
            comercio = self._normalize_text(case.comercio_nombre)
            rango = self._bucket_amount(case.monto_reportado)

            if modus is not None:
                modus_counter[modus] += 1
            if canal is not None:
                canal_counter[canal] += 1
            if categoria is not None:
                categoria_counter[categoria] += 1
            if comercio is not None:
                comercio_counter[comercio] += 1
            if rango is not None:
                rango_monto_counter[rango] += 1
            if case.monto_reportado is not None:
                monto_values.append(float(case.monto_reportado))

            normalized_rows.append(
                {
                    "modus_operandi": modus,
                    "canal_fraude": canal,
                    "comercio_categoria": categoria,
                    "comercio_nombre": comercio,
                    "rango_monto": rango,
                    "monto_reportado": case.monto_reportado,
                }
            )

        indicadores = IndicadoresPatron(
            total_casos=len(cases),
            casos_por_modus_operandi=dict(modus_counter),
            casos_por_canal=dict(canal_counter),
            casos_por_categoria_comercio=dict(categoria_counter),
            casos_por_comercio=dict(comercio_counter),
            casos_por_rango_monto=dict(rango_monto_counter),
            monto_promedio=mean(monto_values) if monto_values else None,
            monto_mediana=median(monto_values) if monto_values else None,
            monto_minimo=min(monto_values) if monto_values else None,
            monto_maximo=max(monto_values) if monto_values else None,
        )

        return indicadores, normalized_rows

    def _detect_concentrations(self, rows: list[dict[str, object]], total_cases: int) -> list[dict[str, object]]:
        if total_cases == 0:
            return []

        concentrations: list[dict[str, object]] = []

        def add_candidate(label: str, counter: Counter[tuple[object, ...]], key_names: list[str], minimum_count: int = 2) -> None:
            if not counter:
                return
            combo, count = counter.most_common(1)[0]
            if count < minimum_count:
                return
            share = count / total_cases
            if share < 0.3:
                return

            details = {
                key_names[i]: combo[i]
                for i in range(len(key_names))
                if combo[i] is not None
            }
            concentrations.append(
                {
                    "label": label,
                    "cases": count,
                    "share": round(share, 4),
                    "details": details,
                }
            )

        combo_counter = Counter(
            (
                row["modus_operandi"],
                row["canal_fraude"],
                row["comercio_categoria"],
            )
            for row in rows
            if row["modus_operandi"] or row["canal_fraude"] or row["comercio_categoria"]
        )
        add_candidate(
            "modus_operandi + canal + categoria_comercio",
            combo_counter,
            ["modus_operandi", "canal_fraude", "comercio_categoria"],
        )

        combo_counter_comercio = Counter(
            (
                row["modus_operandi"],
                row["canal_fraude"],
                row["comercio_nombre"],
            )
            for row in rows
            if row["modus_operandi"] or row["canal_fraude"] or row["comercio_nombre"]
        )
        add_candidate(
            "modus_operandi + canal + comercio",
            combo_counter_comercio,
            ["modus_operandi", "canal_fraude", "comercio_nombre"],
        )

        combo_counter_monto = Counter(
            (
                row["canal_fraude"],
                row["comercio_categoria"],
                row["rango_monto"],
            )
            for row in rows
            if row["canal_fraude"] or row["comercio_categoria"] or row["rango_monto"]
        )
        add_candidate(
            "canal + categoria_comercio + rango_monto",
            combo_counter_monto,
            ["canal_fraude", "comercio_categoria", "rango_monto"],
        )

        concentrations.sort(key=lambda item: (item["cases"], item["share"]), reverse=True)
        return concentrations[:5]

    def _build_llm_context(
        self,
        indicators: IndicadoresPatron,
        concentrations: list[dict[str, object]],
    ) -> str:
        return (
            "Indicadores calculados:\n"
            f"{indicators.model_dump()}\n\n"
            "Concentraciones detectadas:\n"
            f"{concentrations}"
        )

    def process_cases(self, cases: list[CasoA1]) -> ResultadoA2:
        validated_cases = self._validate_cases(cases)
        indicators, rows = self._calculate_indicators(validated_cases)
        concentrations = self._detect_concentrations(rows, indicators.total_casos)

        analysis_timestamp = datetime.now()
        analysis_id = f"ANALYSIS-{analysis_timestamp.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}"

        llm_patterns: list[HipotesisPatron] = []
        if indicators.total_casos > 0:
            try:
                raw_result = self._chain.invoke(
                    {
                        "indicators": indicators.model_dump(),
                        "concentrations": concentrations,
                    }
                )
                if hasattr(raw_result, "model_dump"):
                    parsed = raw_result.model_dump()
                elif isinstance(raw_result, dict):
                    parsed = raw_result
                else:
                    raise TypeError(
                        f"La respuesta del LLM tiene un tipo inesperado: {type(raw_result)!r}."
                    )
                llm_patterns = [HipotesisPatron.model_validate(item) for item in parsed.get("patterns", [])]
            except Exception as exc:
                if concentrations:
                    raise ValueError(f"La respuesta del LLM no cumple el esquema esperado para A2: {exc}") from exc
                llm_patterns = []

        if not concentrations:
            llm_patterns = []

        try:
            return ResultadoA2(
                analysis_id=analysis_id,
                timestamp=analysis_timestamp,
                cases_analyzed=indicators.total_casos,
                indicators=indicators,
                patterns=llm_patterns,
            )
        except Exception as exc:
            raise ValueError(f"La salida final de A2 no cumple el esquema ResultadoA2: {exc}") from exc
