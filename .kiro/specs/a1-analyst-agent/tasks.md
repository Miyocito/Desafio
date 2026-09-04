# Plan de Implementación: Agente A1 — Analista de Casos

## Descripción General

Implementar el módulo A1 del pipeline multi-agente de detección de fraude bancario. El agente extrae entidades estructuradas de transcripciones de llamadas usando Google Gemini 1.5 Flash a través de un pipeline LangChain LCEL, valida los resultados con Pydantic v2 y expone una interfaz Streamlit para procesamiento en lote.

## Tareas

- [ ] 1. Configurar estructura del proyecto y dependencias
  - Crear el directorio `agents/`, `models/` y `data/`
  - Crear `requirements.txt` con las dependencias: `google-generativeai>=0.7.0`, `langchain>=0.2.0`, `langchain-core>=0.2.0`, `langchain-google-genai>=1.0.0`, `pydantic>=2.7.0`, `streamlit>=1.35.0`, `pandas>=2.2.0`, `python-dotenv>=1.0.0`
  - Crear `.env.example` con la variable `GEMINI_API_KEY=your_google_ai_api_key_here`
  - Crear `data/template.csv` con columnas `case_id,fecha_llamada,duracion_segundos,transcripcion_texto,etiqueta_fraude_real` y sin filas de datos
  - Crear archivos `__init__.py` vacíos en `agents/` y `models/`
  - _Requirements: 8.1, 8.2_

- [ ] 2. Implementar modelos Pydantic v2 en `models/schemas.py`
  - [ ] 2.1 Definir enums `ModusOperandi` y `CanalFraude`
    - `ModusOperandi`: `phishing`, `clonacion_tarjeta`, `fraude_digital`, `transferencia_no_autorizada`, `otros`
    - `CanalFraude`: `ATM`, `online`, `POS`, `telefono`
    - _Requirements: 5.3, 5.4_

  - [ ] 2.2 Definir modelos anidados `UbicacionGeografica` y `DatosCliente`
    - `UbicacionGeografica`: `ciudad: str | None`, `pais: str | None`
    - `DatosCliente`: `edad_aproximada: int | None`, `tipo_cuenta: str | None` (sin nombre ni documento)
    - _Requirements: 5.5, 5.6_

  - [ ] 2.3 Definir modelo principal `CasoExtraido` con todos sus campos
    - Campos obligatorios: `case_id`, `timestamp`, `transcript_text`, `status`
    - Campos opcionales LLM: `monto_reportado`, `moneda`, `comercio_nombre`, `comercio_categoria`, `modus_operandi`, `canal_fraude`
    - Campos con `default_factory`: `ubicacion_geografica`, `datos_cliente`, `entidades_adicionales`
    - Campo con validación de rango: `nivel_confianza_extraccion` con `ge=0.0, le=1.0` y `field_validator`
    - _Requirements: 5.1, 5.2, 5.7, 5.8, 5.9_

  - [ ]* 2.4 Escribir test de propiedad para `CasoExtraido`
    - **Propiedad 11: `nivel_confianza_extraccion` rechaza valores fuera de rango**
    - **Valida: Requirements 5.7**

- [ ] 3. Checkpoint — Verificar que los modelos Pydantic compilan y validan correctamente
  - Asegurarse de que todos los tests pasan. Consultar al usuario si surgen dudas.

- [ ] 4. Implementar el logger estructurado en `agents/a1_analyst.py`
  - [ ] 4.1 Crear clase `_JSONFormatter` que emite registros como líneas JSON
    - Incluir campos: `ts`, `level`, `msg` más campos extra opcionales: `case_id`, `attempt`, `status`, `confidence`, `error`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 4.2 Escribir test de propiedad para los logs de errores
    - **Propiedad 10: Los logs de errores contienen los campos obligatorios**
    - **Valida: Requirements 4.4, 6.3, 6.4**

- [ ] 5. Implementar el pipeline LCEL y los prompts en `agents/a1_analyst.py`
  - [ ] 5.1 Definir las constantes de prompts: `PRIMARY_SYSTEM`, `PRIMARY_USER`, `RETRY_SYSTEM`, `RETRY_USER`
    - El prompt principal solicita todos los campos con instrucciones en español
    - El prompt de reintento es más restrictivo y muestra la estructura JSON exacta
    - _Requirements: 3.1, 3.2, 4.1_

  - [ ]* 5.2 Escribir test de propiedad para la construcción de prompts
    - **Propiedad 6: El prompt siempre contiene la transcripción original**
    - **Valida: Requirements 3.1**

  - [ ] 5.3 Implementar `_build_pipeline(system_prompt, user_template)` dentro de `A1Analyst`
    - Instanciar `ChatGoogleGenerativeAI` con `model="gemini-1.5-flash"`, `temperature=0.1`, `max_output_tokens=1024`
    - Construir cadena: `ChatPromptTemplate | ChatGoogleGenerativeAI | JsonOutputParser()`
    - _Requirements: 3.2, 7.4_

- [ ] 6. Implementar la clase `A1Analyst` con lógica de extracción y reintentos
  - [ ] 6.1 Implementar `__init__` con validación de `GEMINI_API_KEY`
    - Parámetros: `max_retries: int = 2`, `confidence_threshold: float = 0.5`
    - Lanzar `EnvironmentError` si la variable de entorno no está definida
    - Construir `_primary_pipeline` y `_retry_pipeline` en el constructor
    - _Requirements: 7.4, 7.5, 8.3_

  - [ ] 6.2 Implementar `_attempt_extraction` con manejo de excepciones
    - Invocar el pipeline con `{"transcript": transcript}`
    - Inyectar `case_id`, `timestamp`, `transcript_text` y `status` por defecto antes de validar
    - Capturar toda excepción, emitir log `WARNING` y retornar `None`
    - _Requirements: 3.3, 4.1, 6.1, 6.3_

  - [ ] 6.3 Implementar `_assign_status` basado en `nivel_confianza_extraccion`
    - `>= confidence_threshold` → `"extracted"`; `< confidence_threshold` → `"low_confidence"`
    - Usar `model_copy(update={...})` de Pydantic v2
    - _Requirements: 3.4, 3.5_

  - [ ]* 6.4 Escribir test de propiedad para asignación de status
    - **Propiedad 7: Asignación de status es consistente con el umbral de confianza**
    - **Valida: Requirements 3.4, 3.5, 7.5**

  - [ ] 6.5 Implementar `_make_failed_case` para construir el objeto fallido
    - Poblar solo `case_id`, `timestamp`, `transcript_text`, `status="extraction_failed"`, `nivel_confianza_extraccion=0.0`
    - _Requirements: 4.3_

  - [ ] 6.6 Implementar `process_case` con bucle de reintentos
    - Parsear `case_id` desde `row["case_id"]`, `timestamp` desde `row["fecha_llamada"]`, `transcript` desde `row["transcripcion_texto"]`
    - Iterar hasta `max_retries`: usar `_primary_pipeline` en intento 1, `_retry_pipeline` en intento 2
    - Retornar resultado de `_assign_status` al primer éxito; si ambos fallan, retornar `_make_failed_case` con log `ERROR`
    - _Requirements: 3.6, 4.1, 4.2, 4.3, 4.4, 6.1, 6.2, 6.4, 6.5_

  - [ ]* 6.7 Escribir test de propiedad para el límite de reintentos
    - **Propiedad 9: El número de reintentos nunca excede `max_retries`**
    - **Valida: Requirements 4.1, 4.2, 4.3**

  - [ ]* 6.8 Escribir test de propiedad para preservación de campos fijos
    - **Propiedad 8: Los campos fijos siempre se preservan desde el CSV**
    - **Valida: Requirements 3.6**

  - [ ] 6.9 Implementar `process_batch` como iteración sobre `process_case`
    - Retornar `[self.process_case(row) for row in cases]` preservando el orden
    - _Requirements: 7.1, 7.2_

  - [ ]* 6.10 Escribir test de propiedad para preservación del orden del batch
    - **Propiedad 3: El orden del batch se preserva**
    - **Valida: Requirements 2.3, 7.2**

  - [ ]* 6.11 Escribir test de propiedad para el tamaño del batch
    - **Propiedad 12: `process_case` preserva el tamaño del batch**
    - **Valida: Requirements 7.1, 7.2**

- [ ] 7. Checkpoint — Asegurarse de que el agente A1 es importable y sus funciones públicas responden correctamente (sin llamadas reales al LLM)
  - Asegurarse de que todos los tests pasan. Consultar al usuario si surgen dudas.

- [ ] 8. Implementar la UI Streamlit en `app.py`
  - [ ] 8.1 Implementar función `validate_csv(df)` que retorna lista de columnas faltantes
    - Columnas requeridas: `case_id`, `fecha_llamada`, `duracion_segundos`, `transcripcion_texto`, `etiqueta_fraude_real`
    - _Requirements: 1.2, 1.3_

  - [ ]* 8.2 Escribir test de propiedad para la validación de columnas CSV
    - **Propiedad 1: Validación de columnas acepta solo el conjunto exacto**
    - **Valida: Requirements 1.2, 1.3**

  - [ ] 8.3 Implementar función `results_to_jsonl(results)` para serializar a JSONL
    - Usar `r.model_dump_json(mode="json")` por cada resultado y unir con `\n`
    - _Requirements: 2.5_

  - [ ]* 8.4 Escribir test de propiedad para la serialización JSONL (round-trip)
    - **Propiedad 5: Serialización JSONL es reversible (round-trip)**
    - **Valida: Requirements 2.5**

  - [ ] 8.5 Implementar la función `main()` de Streamlit con `st.file_uploader`
    - Aceptar solo `.csv`; mostrar error si faltan columnas; mostrar aviso si el CSV está vacío
    - Mostrar número total de casos detectados y vista previa con `st.dataframe` (5 primeras filas)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ] 8.6 Implementar el bucle de procesamiento batch con barra de progreso y logs en tiempo real
    - Usar `st.progress` actualizado tras cada caso
    - Mostrar icono + case_id + status + confianza en un área de log acumulativa
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 8.7 Escribir test de propiedad para el conteo de casos en la UI
    - **Propiedad 2: Conteo de casos es exacto**
    - **Valida: Requirements 1.5**

  - [ ] 8.8 Implementar el resumen final y el botón de descarga JSONL
    - Mostrar `st.metric` por cada status: `extracted`, `low_confidence`, `extraction_failed`
    - Agregar `st.download_button` para descarga del archivo `.jsonl`
    - _Requirements: 2.4, 2.5_

  - [ ]* 8.9 Escribir test de propiedad para la consistencia del resumen
    - **Propiedad 4: Resumen de resultados es consistente con los datos**
    - **Valida: Requirements 2.4**

- [ ] 9. Checkpoint final — Asegurarse de que todos los tests pasan y la aplicación arranca correctamente
  - Asegurarse de que todos los tests pasan. Consultar al usuario si surgen dudas.

## Notas

- Las tareas marcadas con `*` son opcionales y pueden omitirse para una implementación MVP más rápida
- Cada tarea referencia requisitos específicos para trazabilidad completa
- Los checkpoints garantizan validación incremental antes de continuar
- Los tests de propiedad validan las propiedades de corrección universales definidas en el diseño
- Los tests unitarios validan casos específicos y condiciones de borde
- El agente A1 debe ser importable sin efectos secundarios; la UI Streamlit no se inicializa al importar `a1_analyst.py`
- La `GEMINI_API_KEY` se lee exclusivamente de variables de entorno; nunca debe hardcodearse

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3"] },
    { "id": 3, "tasks": ["2.4", "4.1"] },
    { "id": 4, "tasks": ["4.2", "5.1"] },
    { "id": 5, "tasks": ["5.2", "5.3"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "6.5"] },
    { "id": 8, "tasks": ["6.4", "6.6"] },
    { "id": 9, "tasks": ["6.7", "6.8", "6.9"] },
    { "id": 10, "tasks": ["6.10", "6.11", "8.1"] },
    { "id": 11, "tasks": ["8.2", "8.3"] },
    { "id": 12, "tasks": ["8.4", "8.5"] },
    { "id": 13, "tasks": ["8.6"] },
    { "id": 14, "tasks": ["8.7", "8.8"] },
    { "id": 15, "tasks": ["8.9"] }
  ]
}
```
