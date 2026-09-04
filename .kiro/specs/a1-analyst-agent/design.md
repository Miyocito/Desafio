# Diseño Técnico — Agente 1: Analista de Casos (A1)

## Introducción

Este documento describe la arquitectura técnica del Agente Analista de Casos (A1), primer nodo del pipeline multi-agente de detección de fraude bancario. A1 transforma transcripciones de texto desestructuradas en objetos JSON estructurados y validados mediante un pipeline LangChain LCEL sobre Google Gemini 1.5 Flash.

---

## 1. Diagrama de Flujo del Pipeline A1

```
┌─────────────────────────────────────────────────────────────────────┐
│                        UI Streamlit (app.py)                        │
│                                                                     │
│  [st.file_uploader] ──► [Validar columnas CSV] ──► [Mostrar N casos]│
│         │                                                           │
│         ▼                                                           │
│  [Botón "Iniciar procesamiento"]                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────────────────┐                                   │
│  │   process_batch(cases)       │                                   │
│  │   agents/a1_analyst.py       │                                   │
│  └──────────┬───────────────────┘                                   │
│             │ para cada caso                                        │
│             ▼                                                       │
│  [st.progress(i/n)]  [log: case_id + status]                       │
│             │                                                       │
│  [Resumen por status]  [Botón descarga JSONL]                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     process_case(row) — A1                          │
│                                                                     │
│  row dict ──► [Extraer case_id, timestamp, transcript]              │
│                       │                                             │
│                       ▼                                             │
│              ┌─────────────────┐                                    │
│              │  Intento 1      │                                    │
│              │  build_prompt() │                                    │
│              │       │         │                                    │
│              │       ▼         │                                    │
│              │  LCEL pipeline  │                                    │
│              │  prompt │ LLM │ parser                              │
│              │       │         │                                    │
│              │       ▼         │                                    │
│              │  Pydantic v2    │                                    │
│              │  validate()     │                                    │
│              └──────┬──────────┘                                    │
│                     │                                               │
│              ┌──────▼──────────────────────────┐                   │
│              │  ¿Validación exitosa?            │                   │
│              │  SÍ ──► asignar status           │                   │
│              │         (extracted / low_conf.)  │                   │
│              │  NO ──► log WARNING (intento 1)  │                   │
│              └──────┬───────────────────────────┘                   │
│                     │ (en caso de fallo)                            │
│                     ▼                                               │
│              ┌─────────────────┐                                    │
│              │  Intento 2      │                                    │
│              │  build_retry_   │                                    │
│              │  prompt()       │                                    │
│              │       │         │                                    │
│              │       ▼         │                                    │
│              │  LCEL pipeline  │                                    │
│              │       │         │                                    │
│              │       ▼         │                                    │
│              │  Pydantic v2    │                                    │
│              │  validate()     │                                    │
│              └──────┬──────────┘                                    │
│                     │                                               │
│              ┌──────▼──────────────────────────┐                   │
│              │  ¿Validación exitosa?            │                   │
│              │  SÍ ──► asignar status           │                   │
│              │  NO ──► log ERROR                │                   │
│              │         status: extraction_failed│                   │
│              └──────┬───────────────────────────┘                   │
│                     │                                               │
│                     ▼                                               │
│              CasoExtraido ──► retornar a batch                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Estructura de Módulos y Clases

### 2.1 Árbol de archivos del proyecto

```
proyecto/
├── agents/
│   └── a1_analyst.py          # Lógica pura del agente A1
├── app.py                     # UI Streamlit
├── models/
│   └── schemas.py             # Modelos Pydantic v2
├── data/
│   └── template.csv           # Plantilla vacía con columnas correctas
├── requirements.txt           # Dependencias del proyecto
└── .env.example               # Ejemplo de variables de entorno
```

### 2.2 `models/schemas.py` — Modelos Pydantic v2

```python
from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ModusOperandi(str, Enum):
    PHISHING = "phishing"
    CLONACION_TARJETA = "clonacion_tarjeta"
    FRAUDE_DIGITAL = "fraude_digital"
    TRANSFERENCIA_NO_AUTORIZADA = "transferencia_no_autorizada"
    OTROS = "otros"


class CanalFraude(str, Enum):
    ATM = "ATM"
    ONLINE = "online"
    POS = "POS"
    TELEFONO = "telefono"


class UbicacionGeografica(BaseModel):
    ciudad: str | None = None
    pais: str | None = None


class DatosCliente(BaseModel):
    """Datos anonimizados del cliente — sin nombre ni documento."""
    edad_aproximada: int | None = None
    tipo_cuenta: str | None = None


class CasoExtraido(BaseModel):
    # Campos obligatorios poblados desde el CSV, nunca del LLM
    case_id: str
    timestamp: datetime
    transcript_text: str
    status: Literal["extracted", "low_confidence", "extraction_failed"]

    # Campos opcionales extraídos por el LLM
    monto_reportado: float | None = None
    moneda: str | None = None
    comercio_nombre: str | None = None
    comercio_categoria: str | None = None
    modus_operandi: ModusOperandi | None = None
    canal_fraude: CanalFraude | None = None

    # Modelos anidados
    ubicacion_geografica: UbicacionGeografica = Field(
        default_factory=UbicacionGeografica
    )
    datos_cliente: DatosCliente = Field(
        default_factory=DatosCliente
    )

    # Campo con validación de rango
    nivel_confianza_extraccion: float = Field(
        default=0.0, ge=0.0, le=1.0
    )

    # Campo libre para entidades adicionales
    entidades_adicionales: dict[str, Any] = Field(default_factory=dict)

    @field_validator("nivel_confianza_extraccion")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"nivel_confianza_extraccion debe estar en [0.0, 1.0], "
                f"se recibió: {v}"
            )
        return v
```

### 2.3 `agents/a1_analyst.py` — Estructura de clases

```python
# Interfaces y responsabilidades principales

class A1Analyst:
    """
    Agente Analista de Casos.
    
    Responsabilidades:
    - Construir prompts a partir de filas CSV
    - Orquestar el pipeline LCEL (prompt → LLM → parser)
    - Aplicar lógica de reintentos (máx. 2 intentos)
    - Asignar status según nivel de confianza y éxito de validación
    - Emitir logs estructurados
    
    Parámetros configurables:
    - max_retries: int (default=2) — número máximo de intentos LLM
    - confidence_threshold: float (default=0.5) — umbral para "extracted"
    """
    
    def __init__(
        self,
        max_retries: int = 2,
        confidence_threshold: float = 0.5
    ) -> None: ...

    def process_case(self, row: dict) -> CasoExtraido:
        """
        Procesa una fila del CSV y retorna un CasoExtraido.
        Función pública principal — consumible por A2–A5.
        """
        ...

    def process_batch(self, cases: list[dict]) -> list[CasoExtraido]:
        """
        Procesa una lista de filas y retorna la lista de resultados.
        Preserva el orden de entrada.
        """
        ...

    def _build_primary_prompt(self, transcript: str) -> str:
        """Construye el prompt principal de extracción en español."""
        ...

    def _build_retry_prompt(self, transcript: str) -> str:
        """Construye el prompt de reintento, más restrictivo y explícito."""
        ...

    def _build_pipeline(self) -> Runnable:
        """Construye y retorna el pipeline LCEL: prompt | llm | parser."""
        ...

    def _attempt_extraction(
        self,
        row: dict,
        prompt_text: str,
        attempt_number: int
    ) -> CasoExtraido | None:
        """
        Intenta una extracción con el prompt dado.
        Retorna CasoExtraido si tiene éxito, None si falla.
        """
        ...

    def _assign_status(
        self,
        caso: CasoExtraido
    ) -> CasoExtraido:
        """
        Asigna status basado en nivel_confianza_extraccion
        respecto a confidence_threshold.
        """
        ...

    def _make_failed_case(self, row: dict) -> CasoExtraido:
        """
        Crea un CasoExtraido con status extraction_failed
        a partir de los campos disponibles de la fila CSV.
        """
        ...
```

---

## 3. Diseño del Pipeline LCEL

### 3.1 Construcción de la cadena

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence

def _build_pipeline(self) -> RunnableSequence:
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=os.environ["GEMINI_API_KEY"],
        temperature=0.1,         # baja temperatura para extracción determinista
        max_output_tokens=1024,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{user_message}"),
    ])
    parser = JsonOutputParser()
    return prompt | llm | parser
```

### 3.2 Prompt Principal (Intento 1)

```
SYSTEM_PROMPT = """
Eres un analista experto en detección de fraude bancario. 
Tu tarea es extraer entidades clave de transcripciones de llamadas 
de atención al cliente y estructurarlas en formato JSON.

Debes extraer exactamente los siguientes campos:
- monto_reportado: número flotante del monto involucrado (o null)
- moneda: código de moneda ISO 4217 (ej. "USD", "PEN") o null
- comercio_nombre: nombre del comercio mencionado (o null)
- comercio_categoria: categoría del comercio (o null)
- modus_operandi: uno de [phishing, clonacion_tarjeta, fraude_digital, 
  transferencia_no_autorizada, otros] o null
- canal_fraude: uno de [ATM, online, POS, telefono] o null
- ubicacion_geografica: objeto con "ciudad" (str|null) y "pais" (str|null)
- datos_cliente: objeto con "edad_aproximada" (int|null) y 
  "tipo_cuenta" (str|null). NUNCA incluir nombre ni documento.
- entidades_adicionales: objeto con cualquier dato relevante adicional
- nivel_confianza_extraccion: número entre 0.0 y 1.0 indicando 
  tu nivel de confianza en la extracción realizada

Responde ÚNICAMENTE con el JSON sin markdown, sin explicaciones, 
sin bloques de código. Solo el objeto JSON puro.
"""

USER_TEMPLATE = """
Transcripción a analizar:

{transcript}

Extrae las entidades de fraude según las instrucciones del sistema.
Responde solo con el JSON.
"""
```

### 3.3 Prompt de Reintento (Intento 2)

```
RETRY_SYSTEM_PROMPT = """
Eres un analista de fraude bancario. DEBES responder ÚNICAMENTE con 
un objeto JSON válido. Ningún texto adicional. Ningún bloque markdown.
Solo JSON puro que comience con { y termine con }.

Extrae los siguientes campos de la transcripción:
{
  "monto_reportado": <float o null>,
  "moneda": <string o null>,
  "comercio_nombre": <string o null>,
  "comercio_categoria": <string o null>,
  "modus_operandi": <"phishing"|"clonacion_tarjeta"|"fraude_digital"|
                    "transferencia_no_autorizada"|"otros"|null>,
  "canal_fraude": <"ATM"|"online"|"POS"|"telefono"|null>,
  "ubicacion_geografica": {"ciudad": <string o null>, "pais": <string o null>},
  "datos_cliente": {"edad_aproximada": <int o null>, "tipo_cuenta": <string o null>},
  "entidades_adicionales": {},
  "nivel_confianza_extraccion": <float entre 0.0 y 1.0>
}

IMPORTANTE: Responde SOLO con el JSON. Sin texto previo. Sin explicaciones.
"""

RETRY_USER_TEMPLATE = """
Transcripción:

{transcript}

JSON:
"""
```

### 3.4 Flujo de ejecución del pipeline

```
Entrada: row dict (case_id, fecha_llamada, duracion_segundos,
                    transcripcion_texto, etiqueta_fraude_real)
         │
         ▼
Extraer campos fijos: case_id, timestamp ← fecha_llamada
                      transcript_text ← transcripcion_texto
         │
         ▼
Construir prompt principal con transcript_text
         │
         ▼
pipeline.invoke({"user_message": prompt_text})
         │ dict (resultado del JsonOutputParser)
         ▼
Añadir case_id, timestamp, transcript_text al dict
         │
         ▼
CasoExtraido.model_validate(dict)
         │
    ┌────┴──────────────────┐
    │ Éxito                 │ ValidationError
    ▼                       ▼
_assign_status()     log WARNING (intento 1)
retornar             construir retry prompt
                            │
                            ▼
                     pipeline.invoke(retry_prompt)
                            │
                       ┌────┴──────────────────┐
                       │ Éxito                 │ Error
                       ▼                       ▼
               _assign_status()      log ERROR
               retornar              _make_failed_case()
                                     retornar
```

---

## 4. Estrategia de Manejo de Errores y Reintentos

### 4.1 Jerarquía de errores esperados

| Tipo de Error | Origen | Tratamiento |
|---|---|---|
| `pydantic.ValidationError` | Respuesta LLM con JSON inválido | Reintento con prompt alternativo |
| `json.JSONDecodeError` | LLM devuelve texto no-JSON | Reintento con prompt alternativo |
| `google.api_core.exceptions.GoogleAPIError` | Fallo de red / cuota | Re-raise con log ERROR |
| `KeyError` | Fila CSV con columna faltante | Validar antes de process_case |
| `EnvironmentError` | GEMINI_API_KEY no definida | Excepción en `__init__` |

### 4.2 Lógica de reintentos detallada

```python
def process_case(self, row: dict) -> CasoExtraido:
    # Campos fijos (nunca vienen del LLM)
    case_id = str(row["case_id"])
    timestamp = parse_datetime(row["fecha_llamada"])
    transcript = str(row["transcripcion_texto"])

    for attempt in range(1, self.max_retries + 1):
        prompt = (
            self._build_primary_prompt(transcript)
            if attempt == 1
            else self._build_retry_prompt(transcript)
        )
        
        self._log_attempt_start(case_id, attempt)
        
        result = self._attempt_extraction(
            case_id, timestamp, transcript, prompt, attempt
        )
        
        if result is not None:
            final = self._assign_status(result)
            self._log_success(final)
            return final
        
        # Si llegamos aquí, el intento falló
        if attempt < self.max_retries:
            # Continuar al siguiente intento
            continue
    
    # Ambos intentos fallaron
    failed = self._make_failed_case(case_id, timestamp, transcript)
    self._log_final_failure(case_id)
    return failed
```

### 4.3 Política de status según confianza

```
nivel_confianza_extraccion  │  status asignado
───────────────────────────────────────────────
[confidence_threshold, 1.0] │  "extracted"
[0.0, confidence_threshold) │  "low_confidence"
N/A (fallo de validación)   │  "extraction_failed"
```

### 4.4 Estructura de `_make_failed_case`

Cuando ambos intentos fallan, se construye un `CasoExtraido` mínimo:

```python
CasoExtraido(
    case_id=case_id,
    timestamp=timestamp,
    transcript_text=transcript,
    status="extraction_failed",
    nivel_confianza_extraccion=0.0,
    # Todos los demás campos quedan en None o default_factory
)
```

---

## 5. Diseño del Logging Estructurado

### 5.1 Configuración del logger

```python
import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """Formateador que emite cada registro como una línea JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Añadir campos extra si existen
        for key in ("case_id", "attempt", "status", "confidence", "error"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry, ensure_ascii=False)

logger = logging.getLogger("a1_analyst")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
```

### 5.2 Eventos de log por tipo

| Evento | Nivel | Campos obligatorios |
|---|---|---|
| Inicio de extracción | INFO | case_id, attempt |
| Extracción exitosa | INFO | case_id, status, confidence |
| Error de validación Pydantic | WARNING | case_id, attempt, error |
| Error de parseo JSON | WARNING | case_id, attempt, error |
| Caso marcado como extraction_failed | ERROR | case_id, reason |

---

## 6. Diseño de la UI Streamlit

### 6.1 Layout y flujo de pantalla

```
┌──────────────────────────────────────────────────────────────────┐
│  🏦  Agente A1 — Analista de Casos de Fraude                     │
│  ─────────────────────────────────────────────────────────────── │
│                                                                  │
│  [📤 Cargar CSV de transcripciones]                              │
│  Formato esperado: case_id, fecha_llamada, duracion_segundos,    │
│  transcripcion_texto, etiqueta_fraude_real                       │
│                                                                  │
│  ── (tras carga exitosa) ──────────────────────────────────────  │
│  ✅ Archivo válido · 47 casos detectados                         │
│  [Vista previa — primeras 5 filas]                               │
│                                                                  │
│  [▶ Iniciar Procesamiento]                                       │
│                                                                  │
│  ── (durante procesamiento) ───────────────────────────────────  │
│  Progreso: ████████████░░░░░░░░░░  24/47                        │
│                                                                  │
│  Log en tiempo real:                                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ✅ CASE-001 → extracted (confianza: 0.92)                │   │
│  │ ✅ CASE-002 → extracted (confianza: 0.78)                │   │
│  │ ⚠️  CASE-003 → low_confidence (confianza: 0.31)          │   │
│  │ ❌ CASE-004 → extraction_failed                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ── (tras completar) ──────────────────────────────────────────  │
│  📊 Resumen de resultados                                        │
│  ┌─────────────────────┐                                        │
│  │ extracted        38 │                                        │
│  │ low_confidence    6 │                                        │
│  │ extraction_failed 3 │                                        │
│  └─────────────────────┘                                        │
│                                                                  │
│  [⬇ Descargar resultados (.jsonl)]                              │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Implementación de `app.py`

```python
import streamlit as st
import pandas as pd
import json
from io import StringIO
from agents.a1_analyst import A1Analyst

REQUIRED_COLUMNS = {
    "case_id", "fecha_llamada", "duracion_segundos",
    "transcripcion_texto", "etiqueta_fraude_real"
}

def validate_csv(df: pd.DataFrame) -> list[str]:
    """Retorna lista de columnas faltantes (vacía = válido)."""
    return sorted(REQUIRED_COLUMNS - set(df.columns))

def results_to_jsonl(results: list) -> str:
    """Serializa lista de CasoExtraido a JSON Lines."""
    lines = [
        r.model_dump_json(mode="json")
        for r in results
    ]
    return "\n".join(lines)

def main():
    st.set_page_config(
        page_title="A1 — Analista de Casos",
        page_icon="🏦",
        layout="wide"
    )
    st.title("🏦 Agente A1 — Analista de Casos de Fraude")
    
    # ── Fase 1: Carga del CSV ─────────────────────────────────────
    uploaded = st.file_uploader(
        "Cargar CSV de transcripciones",
        type=["csv"],
        help="Columnas requeridas: case_id, fecha_llamada, "
             "duracion_segundos, transcripcion_texto, etiqueta_fraude_real"
    )
    
    if uploaded is None:
        st.info("Sube un archivo CSV para comenzar.")
        return
    
    df = pd.read_csv(uploaded)
    
    # Validación de columnas
    missing = validate_csv(df)
    if missing:
        st.error(
            f"❌ Columnas faltantes: {', '.join(missing)}"
        )
        return
    
    if df.empty:
        st.warning("⚠️ El archivo no contiene filas de datos.")
        return
    
    st.success(f"✅ Archivo válido · **{len(df)} casos** detectados")
    st.dataframe(df.head(5), use_container_width=True)
    
    # ── Fase 2: Procesamiento batch ───────────────────────────────
    if st.button("▶ Iniciar Procesamiento", type="primary"):
        agent = A1Analyst()
        cases = df.to_dict(orient="records")
        results = []
        
        progress_bar = st.progress(0)
        log_container = st.container()
        log_lines = []
        
        for i, row in enumerate(cases):
            result = agent.process_case(row)
            results.append(result)
            
            # Actualizar barra de progreso
            progress_bar.progress((i + 1) / len(cases))
            
            # Añadir línea al log visual
            icon = {
                "extracted": "✅",
                "low_confidence": "⚠️",
                "extraction_failed": "❌"
            }[result.status]
            
            conf_str = (
                f" (confianza: {result.nivel_confianza_extraccion:.2f})"
                if result.status != "extraction_failed"
                else ""
            )
            log_lines.append(
                f"{icon} {result.case_id} → {result.status}{conf_str}"
            )
            
            with log_container:
                st.code("\n".join(log_lines), language=None)
        
        # ── Fase 3: Resumen y descarga ────────────────────────────
        st.subheader("📊 Resumen de resultados")
        
        status_counts = {}
        for r in results:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
        
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Extraídos", status_counts.get("extracted", 0))
        col2.metric("⚠️ Baja confianza", status_counts.get("low_confidence", 0))
        col3.metric("❌ Fallidos", status_counts.get("extraction_failed", 0))
        
        jsonl_content = results_to_jsonl(results)
        st.download_button(
            label="⬇ Descargar resultados (.jsonl)",
            data=jsonl_content,
            file_name="resultados_a1.jsonl",
            mime="application/jsonl",
        )

if __name__ == "__main__":
    main()
```

---

## 7. Implementación de `agents/a1_analyst.py`

```python
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

from models.schemas import CasoExtraido

# ── Prompts ─────────────────────────────────────────────────────────

PRIMARY_SYSTEM = """Eres un analista experto en detección de fraude bancario.
Tu tarea es extraer entidades clave de transcripciones de llamadas de atención
al cliente y estructurarlas en formato JSON.

Extrae exactamente los siguientes campos:
- monto_reportado: número flotante del monto involucrado (o null)
- moneda: código de moneda ISO 4217 (ej. "USD", "PEN") o null
- comercio_nombre: nombre del comercio mencionado (o null)
- comercio_categoria: categoría del comercio (o null)
- modus_operandi: uno de [phishing, clonacion_tarjeta, fraude_digital,
  transferencia_no_autorizada, otros] o null
- canal_fraude: uno de [ATM, online, POS, telefono] o null
- ubicacion_geografica: {{"ciudad": string|null, "pais": string|null}}
- datos_cliente: {{"edad_aproximada": int|null, "tipo_cuenta": string|null}}
  NUNCA incluir nombre ni número de documento.
- entidades_adicionales: {{}} con cualquier dato relevante adicional
- nivel_confianza_extraccion: float en [0.0, 1.0] — tu nivel de confianza

Responde ÚNICAMENTE con JSON puro. Sin markdown. Sin explicaciones."""

PRIMARY_USER = "Transcripción a analizar:\n\n{transcript}"

RETRY_SYSTEM = """Eres un analista de fraude bancario.
DEBES responder ÚNICAMENTE con un objeto JSON válido que empiece con {{
y termine con }}. Sin texto adicional. Sin bloques markdown.

Estructura exacta requerida:
{{
  "monto_reportado": <float o null>,
  "moneda": <string o null>,
  "comercio_nombre": <string o null>,
  "comercio_categoria": <string o null>,
  "modus_operandi": <"phishing"|"clonacion_tarjeta"|"fraude_digital"|"transferencia_no_autorizada"|"otros"|null>,
  "canal_fraude": <"ATM"|"online"|"POS"|"telefono"|null>,
  "ubicacion_geografica": {{"ciudad": <string o null>, "pais": <string o null>}},
  "datos_cliente": {{"edad_aproximada": <int o null>, "tipo_cuenta": <string o null>}},
  "entidades_adicionales": {{}},
  "nivel_confianza_extraccion": <float 0.0-1.0>
}}"""

RETRY_USER = "Transcripción:\n\n{transcript}\n\nJSON:"

# ── Logger con formato JSON ──────────────────────────────────────────

class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for field in ("case_id", "attempt", "status", "confidence", "error"):
            if (val := getattr(record, field, None)) is not None:
                entry[field] = val
        return json.dumps(entry, ensure_ascii=False)


def _get_logger(name: str = "a1_analyst") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(_JSONFormatter())
        log.addHandler(h)
    log.setLevel(logging.DEBUG)
    return log


# ── Agente principal ─────────────────────────────────────────────────

class A1Analyst:
    """Agente Analista de Casos (A1) — extracción de entidades de fraude."""

    def __init__(
        self,
        max_retries: int = 2,
        confidence_threshold: float = 0.5,
    ) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "La variable de entorno GEMINI_API_KEY no está definida. "
                "Configúrala antes de instanciar A1Analyst."
            )
        self.max_retries = max_retries
        self.confidence_threshold = confidence_threshold
        self._logger = _get_logger()
        self._primary_pipeline = self._build_pipeline(
            PRIMARY_SYSTEM, PRIMARY_USER
        )
        self._retry_pipeline = self._build_pipeline(
            RETRY_SYSTEM, RETRY_USER
        )

    def _build_pipeline(
        self, system_prompt: str, user_template: str
    ) -> Runnable:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=os.environ["GEMINI_API_KEY"],
            temperature=0.1,
            max_output_tokens=1024,
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_template),
        ])
        return prompt | llm | JsonOutputParser()

    def _log(
        self, level: int, msg: str, **extra: Any
    ) -> None:
        self._logger.log(level, msg, extra=extra)

    def _attempt_extraction(
        self,
        case_id: str,
        timestamp: datetime,
        transcript: str,
        pipeline: Runnable,
        attempt: int,
    ) -> CasoExtraido | None:
        self._log(
            logging.INFO,
            "Iniciando extracción",
            case_id=case_id,
            attempt=attempt,
        )
        try:
            raw: dict = pipeline.invoke({"transcript": transcript})
            # Inyectar campos fijos antes de validar
            raw["case_id"] = case_id
            raw["timestamp"] = timestamp.isoformat()
            raw["transcript_text"] = transcript
            raw.setdefault("status", "extracted")
            return CasoExtraido.model_validate(raw)
        except Exception as exc:
            self._log(
                logging.WARNING,
                "Fallo en extracción",
                case_id=case_id,
                attempt=attempt,
                error=str(exc),
            )
            return None

    def _assign_status(self, caso: CasoExtraido) -> CasoExtraido:
        if caso.nivel_confianza_extraccion >= self.confidence_threshold:
            status = "extracted"
        else:
            status = "low_confidence"
        return caso.model_copy(update={"status": status})

    def _make_failed_case(
        self,
        case_id: str,
        timestamp: datetime,
        transcript: str,
    ) -> CasoExtraido:
        return CasoExtraido(
            case_id=case_id,
            timestamp=timestamp,
            transcript_text=transcript,
            status="extraction_failed",
            nivel_confianza_extraccion=0.0,
        )

    def process_case(self, row: dict) -> CasoExtraido:
        """Procesa una fila del CSV y retorna CasoExtraido."""
        case_id = str(row["case_id"])
        timestamp = datetime.fromisoformat(str(row["fecha_llamada"]))
        transcript = str(row["transcripcion_texto"])

        pipelines = [self._primary_pipeline, self._retry_pipeline]

        for attempt, pipeline in enumerate(pipelines[: self.max_retries], 1):
            result = self._attempt_extraction(
                case_id, timestamp, transcript, pipeline, attempt
            )
            if result is not None:
                final = self._assign_status(result)
                self._log(
                    logging.INFO,
                    "Extracción completada",
                    case_id=case_id,
                    status=final.status,
                    confidence=final.nivel_confianza_extraccion,
                )
                return final

        # Ambos intentos fallaron
        failed = self._make_failed_case(case_id, timestamp, transcript)
        self._log(
            logging.ERROR,
            "Caso marcado como extraction_failed tras agotar reintentos",
            case_id=case_id,
        )
        return failed

    def process_batch(self, cases: list[dict]) -> list[CasoExtraido]:
        """Procesa una lista de filas preservando el orden de entrada."""
        return [self.process_case(row) for row in cases]
```

---

## 8. Dependencias del Proyecto

```
# requirements.txt
google-generativeai>=0.7.0
langchain>=0.2.0
langchain-core>=0.2.0
langchain-google-genai>=1.0.0
pydantic>=2.7.0
streamlit>=1.35.0
pandas>=2.2.0
python-dotenv>=1.0.0
```

---

## 9. Configuración de Variables de Entorno

```bash
# .env.example
GEMINI_API_KEY=your_google_ai_api_key_here
```

Para ejecutar localmente:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar API key
cp .env.example .env
# editar .env con la clave real

# Lanzar la UI
streamlit run app.py
```

---

## 10. Correctness Properties

*Una propiedad es una característica o comportamiento que debe ser verdadero en todas las ejecuciones válidas del sistema — esencialmente, una declaración formal sobre lo que el sistema debe hacer. Las propiedades sirven como puente entre las especificaciones legibles por humanos y las garantías de corrección verificables por máquina.*

### Property 1: Validación de columnas acepta solo el conjunto exacto

*Para cualquier* DataFrame cargado, la función de validación debe aceptar si y solo si el conjunto de columnas contiene exactamente `{case_id, fecha_llamada, duracion_segundos, transcripcion_texto, etiqueta_fraude_real}`. Para cualquier subconjunto estricto o conjunto con columnas adicionales pero faltantes, debe reportar las columnas faltantes.

**Validates: Requirements 1.2, 1.3**

---

### Property 2: Conteo de casos es exacto

*Para cualquier* DataFrame válido con N filas, la UI debe mostrar exactamente N como número total de casos detectados, independientemente del contenido de las filas.

**Validates: Requirements 1.5**

---

### Property 3: El orden del batch se preserva

*Para cualquier* lista ordenada de filas de CSV de tamaño N, `process_batch` debe retornar exactamente N objetos `CasoExtraido` en el mismo orden que las filas de entrada (el case_id del resultado i debe corresponder al case_id de la fila i).

**Validates: Requirements 2.3, 7.2**

---

### Property 4: Resumen de resultados es consistente con los datos

*Para cualquier* lista de N resultados `CasoExtraido`, el resumen mostrado debe satisfacer: suma(conteos por status) = N, y el conteo de cada status debe ser igual al número de elementos de esa categoría en la lista.

**Validates: Requirements 2.4**

---

### Property 5: Serialización JSONL es reversible (round-trip)

*Para cualquier* lista de objetos `CasoExtraido` válidos, serializarlos a JSONL y luego deserializarlos debe producir objetos equivalentes (mismos valores en todos los campos).

**Validates: Requirements 2.5**

---

### Property 6: El prompt siempre contiene la transcripción original

*Para cualquier* fila CSV con un campo `transcripcion_texto`, el prompt construido (primario o de reintento) debe contener el texto exacto de la transcripción sin modificaciones ni truncamientos.

**Validates: Requirements 3.1**

---

### Property 7: Asignación de status es consistente con el umbral de confianza

*Para cualquier* extracción exitosa con `nivel_confianza_extraccion = c` y agente configurado con `confidence_threshold = t`, el status asignado debe ser `"extracted"` si `c >= t` y `"low_confidence"` si `c < t`. Esto debe mantenerse para cualquier valor de `t` en `(0.0, 1.0)` y cualquier valor de `c` en `[0.0, 1.0]`.

**Validates: Requirements 3.4, 3.5, 7.5**

---

### Property 8: Los campos fijos siempre se preservan desde el CSV

*Para cualquier* fila CSV con `case_id` y `fecha_llamada`, el `CasoExtraido` resultante debe tener `case_id` idéntico al de la fila y `timestamp` igual al valor parseado de `fecha_llamada`, independientemente de lo que retorne el LLM.

**Validates: Requirements 3.6**

---

### Property 9: El número de reintentos nunca excede max_retries

*Para cualquier* caso que falle en todos los intentos, el número total de llamadas al pipeline LLM debe ser exactamente igual a `max_retries` (no más, no menos). El status final debe ser `"extraction_failed"` si todos los intentos fallan.

**Validates: Requirements 4.1, 4.2, 4.3**

---

### Property 10: Los logs de errores contienen los campos obligatorios

*Para cualquier* fallo de validación en cualquier intento, el registro de log emitido debe contener `case_id`, número de intento (`attempt`) y descripción del error (`error`). Para cualquier caso marcado como `extraction_failed`, el log de nivel ERROR debe contener el `case_id`.

**Validates: Requirements 4.4, 6.3, 6.4**

---

### Property 11: nivel_confianza_extraccion rechaza valores fuera de rango

*Para cualquier* valor `v` fuera del intervalo `[0.0, 1.0]`, la creación o validación de un `CasoExtraido` con `nivel_confianza_extraccion = v` debe lanzar `pydantic.ValidationError` sin crear el objeto.

**Validates: Requirements 5.7**

---

### Property 12: process_case preserva el tamaño del batch

*Para cualquier* lista de N filas de CSV válidas pasada a `process_batch`, el resultado debe ser una lista de exactamente N objetos `CasoExtraido`. La función nunca debe silenciosamente descartar ni duplicar filas.

**Validates: Requirements 7.1, 7.2**
