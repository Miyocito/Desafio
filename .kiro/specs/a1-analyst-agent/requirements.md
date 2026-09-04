# Documento de Requisitos — Agente 1: Analista de Casos (A1)

## Introducción

El Agente Analista de Casos (A1) es el primer nodo del pipeline multi-agente de detección de fraude bancario. Su responsabilidad es leer transcripciones de texto desestructuradas provenientes de canales de atención al cliente (cargadas en lote desde un CSV), extraer entidades clave mediante un LLM (Google Gemini 1.5 Flash), y producir un objeto JSON estructurado y validado por Pydantic v2. El resultado es consumido por los agentes A2–A5. La UI Streamlit expone el proceso en modo batch con barra de progreso y logs visibles.

---

## Glosario

- **A1 / Agente Analista**: Módulo `agents/a1_analyst.py` responsable de la extracción de entidades desde transcripciones.
- **CSV de entrada**: Archivo con columnas `case_id`, `fecha_llamada`, `duracion_segundos`, `transcripcion_texto`, `etiqueta_fraude_real`, cargado a través de la UI Streamlit.
- **CasoExtraido**: Modelo Pydantic v2 definido en `models/schemas.py` que representa el resultado estructurado de una extracción exitosa.
- **Extracción**: Proceso de llamada al LLM para obtener entidades del fraude a partir de la `transcripcion_texto`.
- **Pipeline LCEL**: Cadena LangChain construida con `RunnableSequence` / LCEL que encadena el prompt, el LLM y el parser de salida.
- **LLM**: Google Gemini 1.5 Flash accedido mediante la API gratuita de Google AI.
- **Intento de reintento**: Segunda llamada al LLM con un prompt alternativo tras un primer fallo de extracción.
- **status extracted**: Estado del `CasoExtraido` cuando la extracción produjo un resultado válido y completo.
- **status low_confidence**: Estado cuando la extracción es válida pero `nivel_confianza_extraccion` < 0.5.
- **status extraction_failed**: Estado cuando dos intentos consecutivos no producen un JSON válido o completo.
- **Modus Operandi**: Categoría de fraude; valores permitidos: `phishing`, `clonacion_tarjeta`, `fraude_digital`, `transferencia_no_autorizada`, `otros`.
- **Canal de Fraude**: Medio por donde ocurrió el fraude; valores permitidos: `ATM`, `online`, `POS`, `telefono`.
- **nivel_confianza_extraccion**: Valor flotante en el rango [0.0, 1.0] autoevaluado por el LLM al final de cada extracción.
- **Logging estructurado**: Emisión de registros en formato JSON (mediante el módulo estándar `logging` con un `JSONFormatter` o similar) en cada paso relevante del agente.
- **Plantilla CSV**: Archivo `data/template.csv` con las columnas de entrada y sin filas de datos reales.

---

## Requisitos

### Requisito 1 — Carga y Validación del CSV de Entrada

**User Story:** Como operador de fraude, quiero cargar un CSV con transcripciones de llamadas desde la UI, para que el sistema procese los casos en lote sin intervención manual.

#### Criterios de Aceptación

1. THE UI SHALL mostrar un componente `st.file_uploader` que acepte únicamente archivos con extensión `.csv`.
2. WHEN el usuario carga un archivo CSV, THE UI SHALL validar que el archivo contiene exactamente las columnas `case_id`, `fecha_llamada`, `duracion_segundos`, `transcripcion_texto` y `etiqueta_fraude_real`.
3. IF el archivo cargado omite alguna de las columnas requeridas, THEN THE UI SHALL mostrar un mensaje de error que enumere las columnas faltantes y detenga el procesamiento.
4. IF el archivo CSV no contiene filas de datos (está vacío), THEN THE UI SHALL mostrar un aviso informativo y detenga el procesamiento.
5. THE UI SHALL mostrar el número total de casos detectados en el CSV antes de iniciar el procesamiento.

---

### Requisito 2 — Procesamiento en Lote con Retroalimentación Visual

**User Story:** Como operador de fraude, quiero ver el progreso del procesamiento en tiempo real, para que pueda monitorear el avance sin bloquear la interfaz.

#### Criterios de Aceptación

1. WHEN el operador confirma el inicio del procesamiento, THE UI SHALL mostrar una barra de progreso (`st.progress`) que se actualice tras completar la extracción de cada caso.
2. WHILE el procesamiento está en curso, THE UI SHALL mostrar un área de logs en tiempo real con el `case_id` y el `status` resultante de cada caso procesado.
3. THE UI SHALL procesar los casos de forma secuencial, en el orden en que aparecen en el CSV.
4. WHEN todos los casos han sido procesados, THE UI SHALL mostrar un resumen con el conteo de casos por `status` (`extracted`, `low_confidence`, `extraction_failed`).
5. WHEN todos los casos han sido procesados, THE UI SHALL ofrecer un botón para descargar los resultados como un archivo JSON Lines (`.jsonl`).

---

### Requisito 3 — Extracción de Entidades mediante LLM

**User Story:** Como sistema de detección de fraude, quiero que el Agente A1 extraiga entidades clave de cada transcripción, para que los agentes posteriores dispongan de datos estructurados y normalizados.

#### Criterios de Aceptación

1. WHEN A1 recibe una fila del CSV, THE A1 SHALL construir un prompt que incluya la `transcripcion_texto` y las instrucciones de extracción en español.
2. THE A1 SHALL invocar el modelo Google Gemini 1.5 Flash mediante el pipeline LCEL para cada caso procesado.
3. WHEN el LLM devuelve una respuesta, THE A1 SHALL parsear la respuesta y validarla contra el modelo `CasoExtraido` de Pydantic v2.
4. THE A1 SHALL asignar `status: extracted` cuando la validación Pydantic es exitosa y `nivel_confianza_extraccion` >= 0.5.
5. THE A1 SHALL asignar `status: low_confidence` cuando la validación Pydantic es exitosa pero `nivel_confianza_extraccion` < 0.5.
6. THE A1 SHALL poblar el campo `case_id` y `timestamp` directamente desde la fila CSV, sin depender del LLM para esos campos.

---

### Requisito 4 — Lógica de Reintento ante Extracción Fallida

**User Story:** Como sistema de detección de fraude, quiero que A1 reintente la extracción con un prompt alternativo antes de marcar un caso como fallido, para maximizar la tasa de extracción exitosa.

#### Criterios de Aceptación

1. IF el primer intento de extracción produce una respuesta que no valida contra `CasoExtraido`, THEN THE A1 SHALL realizar un segundo intento usando un prompt alternativo más restrictivo que solicita explícitamente formato JSON puro.
2. THE A1 SHALL realizar un máximo de 2 intentos de extracción por caso (intento original + 1 reintento).
3. IF ambos intentos producen respuestas inválidas, THEN THE A1 SHALL crear un objeto `CasoExtraido` con `status: extraction_failed`, los campos disponibles de la fila CSV (`case_id`, `timestamp`, `transcript_text`) y el resto de campos en sus valores por defecto o `None`.
4. THE A1 SHALL registrar en el log estructurado el número de intento y el tipo de error de validación para cada fallo.

---

### Requisito 5 — Modelo de Datos `CasoExtraido`

**User Story:** Como agente A2 (consumidor), quiero recibir un objeto con un contrato de datos estricto, para que pueda procesar los casos sin lógica defensiva adicional.

#### Criterios de Aceptación

1. THE CasoExtraido SHALL contener los campos obligatorios: `case_id` (str), `timestamp` (datetime), `transcript_text` (str), `status` (Literal["extracted", "low_confidence", "extraction_failed"]).
2. THE CasoExtraido SHALL contener los campos opcionales extraídos por el LLM: `monto_reportado` (float | None), `moneda` (str | None), `comercio_nombre` (str | None), `comercio_categoria` (str | None).
3. THE CasoExtraido SHALL contener el campo `modus_operandi` tipado como `Enum` con valores exactos: `phishing`, `clonacion_tarjeta`, `fraude_digital`, `transferencia_no_autorizada`, `otros`; y valor por defecto `None`.
4. THE CasoExtraido SHALL contener el campo `canal_fraude` tipado como `Enum` con valores exactos: `ATM`, `online`, `POS`, `telefono`; y valor por defecto `None`.
5. THE CasoExtraido SHALL contener el campo `ubicacion_geografica` como un modelo anidado con subcampos `ciudad` (str | None) y `pais` (str | None).
6. THE CasoExtraido SHALL contener el campo `datos_cliente` como un modelo anidado con subcampos `edad_aproximada` (int | None) y `tipo_cuenta` (str | None); ambos anonimizados (sin nombre ni documento).
7. THE CasoExtraido SHALL contener el campo `nivel_confianza_extraccion` (float) en el rango [0.0, 1.0] con validador Pydantic que rechace valores fuera de ese rango.
8. THE CasoExtraido SHALL contener el campo `entidades_adicionales` (dict[str, Any]) con valor por defecto de diccionario vacío.
9. THE schemas.py SHALL exportar todos los modelos Pydantic necesarios para que sean importables directamente por A1 y los agentes A2–A5.

---

### Requisito 6 — Logging Estructurado

**User Story:** Como desarrollador del sistema, quiero que A1 emita logs estructurados en cada paso, para que pueda auditar el comportamiento del agente y detectar errores en producción.

#### Criterios de Aceptación

1. THE A1 SHALL emitir un log estructurado al iniciar la extracción de cada caso, incluyendo `case_id` y número de intento.
2. THE A1 SHALL emitir un log estructurado al completar exitosamente la extracción de un caso, incluyendo `case_id`, `status` y `nivel_confianza_extraccion`.
3. THE A1 SHALL emitir un log estructurado al detectar un error de validación Pydantic, incluyendo `case_id`, número de intento y descripción del error.
4. THE A1 SHALL emitir un log estructurado al marcar un caso como `extraction_failed`, incluyendo `case_id` y el motivo del fallo.
5. THE A1 SHALL utilizar niveles de log estándar de Python (`DEBUG`, `INFO`, `WARNING`, `ERROR`) de forma consistente: extracciones exitosas en `INFO`, reintentos en `WARNING`, fallos definitivos en `ERROR`.

---

### Requisito 7 — Modularidad y Reutilización

**User Story:** Como arquitecto del sistema, quiero que A1 sea un módulo desacoplado de la UI, para que los agentes A2–A5 puedan invocarlo directamente sin depender de Streamlit.

#### Criterios de Aceptación

1. THE A1 SHALL exponer una función pública `process_case(row: dict) -> CasoExtraido` que acepte un diccionario con las claves del CSV y retorne un `CasoExtraido`.
2. THE A1 SHALL exponer una función pública `process_batch(cases: list[dict]) -> list[CasoExtraido]` que itere sobre una lista de filas y retorne la lista de resultados.
3. THE A1 SHALL ser importable desde `agents/a1_analyst.py` sin efectos secundarios al importar (sin inicialización de Streamlit ni ejecución automática).
4. THE A1 SHALL leer la API key de Gemini únicamente desde variables de entorno, sin hardcodear credenciales en el código fuente.
5. THE A1 SHALL ser instanciable con parámetros configurables: `max_retries` (int, default=2) y `confidence_threshold` (float, default=0.5), permitiendo ajuste sin modificar el código fuente.

---

### Requisito 8 — Plantilla CSV y Estructura de Proyecto

**User Story:** Como nuevo desarrollador del equipo, quiero una plantilla CSV y una estructura de carpetas clara, para que pueda comenzar a usar el sistema sin ambigüedad.

#### Criterios de Aceptación

1. THE proyecto SHALL incluir el archivo `data/template.csv` con exactamente las columnas `case_id`, `fecha_llamada`, `duracion_segundos`, `transcripcion_texto`, `etiqueta_fraude_real` y sin filas de datos reales.
2. THE proyecto SHALL organizar el código en los módulos: `agents/a1_analyst.py`, `app.py`, `models/schemas.py` y `data/template.csv`.
3. IF la variable de entorno `GEMINI_API_KEY` no está definida al iniciar A1, THEN THE A1 SHALL lanzar una excepción de configuración con un mensaje que indique la variable de entorno requerida.
