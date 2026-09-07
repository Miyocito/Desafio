from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from models.schemas import CasoExtraido, UbicacionGeografica


load_dotenv()


class _ExtraccionA1(BaseModel):
    monto_reportado: float | None = Field(
        default=None,
        description="Monto involucrado en la transacción o reclamo, si aparece explícitamente en la transcripción.",
    )
    moneda: str | None = Field(
        default=None,
        description="Moneda del monto reportado, por ejemplo CLP, USD, PEN, MXN.",
    )
    comercio_nombre: str | None = Field(
        default=None,
        description="Nombre del comercio, plataforma o entidad mencionada.",
    )
    comercio_categoria: str | None = Field(
        default=None,
        description="Categoría del comercio, por ejemplo e-commerce, retail, banca, telecomunicaciones.",
    )
    modus_operandi: str | None = Field(
        default=None,
        description="Resumen breve del modo de fraude observado, usando etiquetas cortas si es posible.",
    )
    canal_fraude: str | None = Field(
        default=None,
        description="Canal asociado al fraude, por ejemplo telefono, sms, email, web, app, presencial.",
    )
    ubicacion_geografica: UbicacionGeografica = Field(
        default_factory=UbicacionGeografica,
        description="Ciudad y país mencionados o inferibles razonablemente desde la transcripción.",
    )
    nivel_confianza_extraccion: float = Field(
        ge=0.0,
        le=1.0,
        description="Confianza estimada de la extracción entre 0 y 1.",
    )


class A1Analyst:
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
Eres un analista de fraude bancario.
Tu única función es extraer información presente en la transcripción.

Debes devolver únicamente una salida estructurada que siga este esquema JSON:
{{
  "monto_reportado": number | null,
  "moneda": string | null,
  "comercio_nombre": string | null,
  "comercio_categoria": string | null,
  "modus_operandi": string | null,
  "canal_fraude": string | null,
  "ubicacion_geografica": {{
    "ciudad": string | null,
    "pais": string | null
  }},
  "nivel_confianza_extraccion": number
}}

Reglas obligatorias:
- No inventes información.
- Si un dato no aparece o no puede inferirse razonablemente, usa null.
- No inventes montos.
- No inventes comercios.
- No inventes ubicaciones.
- La respuesta debe estar basada únicamente en la transcripción.
- La salida debe ser JSON estructurado.
- No incluyas explicaciones fuera del JSON.
- Usa español.
                    """.strip(),
                ),
                (
                    "human",
                    """
Transcripción:
{transcript}

Devuelve solo los campos del esquema esperado.
                    """.strip(),
                ),
            ]
        )

        self._chain = self._prompt | self._llm.with_structured_output(_ExtraccionA1)

    def process_case(self, case_id: str, timestamp: datetime, transcript: str) -> CasoExtraido:
        try:
            raw_result = self._chain.invoke({"transcript": transcript})
        except Exception as exc:
            raise RuntimeError(f"Error al extraer el caso con Gemini: {exc}") from exc

        if hasattr(raw_result, "model_dump"):
            extracted = raw_result.model_dump()
        elif isinstance(raw_result, dict):
            extracted = raw_result
        else:
            raise TypeError(
                f"La respuesta del LLM tiene un tipo inesperado: {type(raw_result)!r}."
            )

        payload = {
            "case_id": case_id,
            "timestamp": timestamp,
            "transcript_text": transcript,
            **extracted,
        }

        try:
            return CasoExtraido.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"La respuesta del LLM no cumple el esquema CasoExtraido: {exc}") from exc
