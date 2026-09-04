# Prototipo de Sistema Multi-Agente para Detección y Certificación de Reglas de Fraude

Este proyecto presenta una solución avanzada e inteligente para la transición de procesos reactivos y manuales hacia un ecosistema automatizado de mitigación de riesgos financieros. Se trata de un sistema de Inteligencia Artificial basado en una **arquitectura multi-agente orquestada de forma secuencial**, diseñada específicamente para identificar modalidades emergentes de fraude, formular hipótesis lógicas y certificar cuantitativamente su efectividad antes de su despliegue en producción.

A partir de transcripciones de texto provenientes de canales de atención (llamadas de soporte, reclamos, etc.), el sistema ejecuta un *pipeline* cerrado de **5 agentes de IA especializados**, garantizando un flujo determinista, auditable y con trazabilidad completa de los datos.

## 🤖 Arquitectura del Pipeline y Flujo de Agentes

El core del sistema está gobernado por una máquina de estados determinista donde cada agente cumple un rol estrictamente delimitado:

1. **Analista de Casos (A1):** Extrae entidades clave (montos, comercios, modus operandi) desde transcripciones desestructuradas y las normaliza en un formato JSON estructurado bajo taxonomías de fraude predefinidas.
2. **Investigador de Patrones (A2):** Agrupa y correlaciona de forma analítica los incidentes procesados por el agente previo para descubrir patrones conductuales, temporales o geográficos, formulando una hipótesis de fraude emergente.
3. **Validador de Hipótesis (A3):** Cruza la hipótesis generada contra el histórico transaccional de la entidad financiera empleando herramientas de análisis de datos para cuantificar la recurrencia, volumen y el impacto económico potencial.
4. **Generador de Reglas (A4):** Traduce de forma automática el patrón validado en una especificación técnica de regla lógica ejecutable (JSON Rule Engine / Python DSL) lista para motores de reglas.
5. **Certificador de Reglas (A5):** Realiza un proceso de *backtesting* masivo inyectando la nueva regla sobre el dataset histórico completo para calcular científicamente las métricas de rendimiento: Tasa de Detección (%), Tasa de Falsos Positivos (%) e Impacto Financiero Evitado.

## 🛠️ Stack Tecnológico Principal

* **Orquestación Multi-Agente:** `LangGraph` + `LangChain` (Garantizando control del no-determinismo y manejo de estado centralizado).
* **Validación de Estructuras:** `Pydantic` para asegurar contratos de datos estrictos en cada nodo del grafo.
* **Procesamiento de Datos:** `Pandas` para la ejecución eficiente de cruces transaccionales y lógica de *backtesting*.
* **Interfaz de Usuario (Demo UI):** `Streamlit` / `Chainlit` para proporcionar visualización interactiva y trazabilidad paso a paso del flujo de ejecución de los agentes.

---
