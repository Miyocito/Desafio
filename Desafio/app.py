"""Demo interactiva del pipeline A1 → A5 de detección de fraude.

Ejecutar con: streamlit run app.py
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from agents.a1_analyst import A1Analyst
from agents.a2_pattern_investigator import A2PatternInvestigator
from agents.a3_hypothesis_validator import A3HypothesisValidator
from agents.a4_rule_generator import A4RuleGenerator
from agents.a5_rule_certifier import A5RuleCertifier
from models.schemas import CasoA1


ROOT = Path(__file__).resolve().parent
INPUT_CASES = ROOT / "data" / "a1_input_cases.csv"
HISTORICAL_DATA = ROOT / "data" / "historical_transactions.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    """Lee el CSV con UTF-8 y no cambia el archivo fuente."""
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def jsonable(model: Any) -> dict[str, Any]:
    """Convierte modelos Pydantic a datos que Streamlit puede renderizar."""
    return model.model_dump(mode="json")


@st.cache_data(show_spinner=False)
def get_input_cases() -> list[dict[str, str]]:
    return read_csv(INPUT_CASES)


@st.cache_data(show_spinner=False)
def get_history_preview() -> list[dict[str, str]]:
    return read_csv(HISTORICAL_DATA)


def execute_pipeline(cases: list[dict[str, str]]) -> dict[str, Any]:
    """Orquesta los agentes usando sólo el histórico existente, en modo lectura."""
    a1, a2 = A1Analyst(), A2PatternInvestigator()
    a3, a4, a5 = A3HypothesisValidator(), A4RuleGenerator(), A5RuleCertifier()

    extracted = [
        a1.process_case(
            case_id=case["case_id"],
            timestamp=datetime.fromisoformat(case["timestamp"]),
            transcript=case["transcript"],
        )
        for case in cases
    ]
    result_a2 = a2.process_cases([CasoA1.model_validate(item.model_dump()) for item in extracted])
    transactions_a3 = a3.load_transactions_from_csv(HISTORICAL_DATA)
    result_a3 = a3.validate_hypotheses(result_a2.patterns, transactions_a3)
    result_a4 = a4.generate_rules(result_a3.results)
    transactions_a5 = a5.load_transactions_from_csv(HISTORICAL_DATA)
    result_a5 = a5.backtest_rules(result_a4.rules, transactions_a5)
    return {"a1": extracted, "a2": result_a2, "a3": result_a3, "a4": result_a4, "a5": result_a5}


def metric(label: str, value: str, help_text: str | None = None) -> None:
    st.metric(label, value, help=help_text)


st.set_page_config(page_title="Fraud Rule Lab", page_icon="🛡️", layout="wide")
st.title("🛡️ Fraud Rule Lab")
st.caption("Demo trazable: transcripciones → patrón → validación histórica → regla → certificación")

cases = get_input_cases()
history = get_history_preview()
fraud_count = sum(row.get("fraude_confirmado", "").strip().lower() == "true" for row in history)

with st.sidebar:
    st.header("Datos de la demo")
    st.caption("Fuentes sintéticas/locales; no se usan datos de clientes reales.")
    st.metric("Transcripciones A1", len(cases))
    st.metric("Transacciones históricas", len(history))
    st.metric("Fraudes etiquetados", fraud_count)
    st.divider()
    st.caption("El pipeline se ejecuta con Gemini y temperatura 0. El histórico se usa en modo sólo lectura.")

tab_data, tab_run, tab_trace, tab_cert = st.tabs(
    ["1. Datos", "2. Ejecutar pipeline", "3. Trazabilidad A1–A4", "4. Certificación A5"]
)

with tab_data:
    left, right = st.columns(2)
    with left:
        st.subheader("Transcripciones de entrada (A1)")
        st.dataframe(cases, use_container_width=True, hide_index=True, height=330)
        st.download_button("Descargar input A1", INPUT_CASES.read_bytes(), "a1_input_cases.csv", "text/csv")
    with right:
        st.subheader("Log transaccional histórico")
        st.dataframe(history, use_container_width=True, hide_index=True, height=330)
        st.download_button("Descargar histórico", HISTORICAL_DATA.read_bytes(), "historical_transactions.csv", "text/csv")

with tab_run:
    st.subheader("Ejecución controlada")
    uploaded_cases = st.file_uploader(
        "Cargar transcripciones CSV (opcional)", type="csv", help="Columnas requeridas: case_id, timestamp, transcript."
    )
    run_cases = cases
    if uploaded_cases is not None:
        try:
            run_cases = list(csv.DictReader(io.StringIO(uploaded_cases.getvalue().decode("utf-8-sig"))))
            required_columns = {"case_id", "timestamp", "transcript"}
            if not run_cases or not required_columns.issubset(run_cases[0]):
                raise ValueError("Faltan las columnas case_id, timestamp o transcript.")
            st.success(f"Archivo cargado: {len(run_cases)} transcripción(es).")
        except (UnicodeDecodeError, ValueError) as exc:
            st.error(f"No se pudo leer el CSV: {exc}")
            run_cases = cases
    selected_ids = st.multiselect(
        "Casos a analizar", [case["case_id"] for case in run_cases], default=[case["case_id"] for case in run_cases]
    )
    chosen_cases = [case for case in run_cases if case["case_id"] in selected_ids]
    st.caption(f"A1 procesará {len(chosen_cases)} transcripción(es). A3 y A5 analizarán las {len(history)} filas del histórico.")

    if st.button("▶ Ejecutar los 5 agentes", type="primary", disabled=not chosen_cases):
        try:
            progress = st.progress(5, text="A1: extrayendo entidades estructuradas…")
            # La orquestación está encapsulada para mantener la UI y contratos separados.
            with st.spinner("Procesando A1 → A5. Puede tardar unos segundos por las llamadas al modelo."):
                result = execute_pipeline(chosen_cases)
            progress.progress(100, text="Pipeline completado")
            st.session_state["pipeline_result"] = result
            st.success("Pipeline finalizado. Revisa la trazabilidad y la certificación.")
        except Exception as exc:
            st.error("No fue posible completar el pipeline.")
            st.exception(exc)
            st.info("Verifica que GEMINI_API_KEY esté configurada en el archivo .env y que el modelo tenga acceso.")

    if "pipeline_result" in st.session_state:
        result = st.session_state["pipeline_result"]
        a5 = result["a5"]
        totals = a5.results
        cols = st.columns(4)
        with cols[0]: metric("Patrones A2", str(len(result["a2"].patterns)))
        with cols[1]: metric("Hipótesis validadas", str(sum(item.validated for item in result["a3"].results)))
        with cols[2]: metric("Reglas generadas", str(a5.rules_tested))
        with cols[3]: metric("Reglas certificadas", str(a5.rules_certified))

with tab_trace:
    if "pipeline_result" not in st.session_state:
        st.info("Ejecuta el pipeline para ver la evidencia intermedia de cada agente.")
    else:
        result = st.session_state["pipeline_result"]
        with st.expander("A1 · Casos extraídos", expanded=True):
            st.json([jsonable(item) for item in result["a1"]], expanded=False)
        with st.expander("A2 · Hipótesis e indicadores", expanded=True):
            st.json(jsonable(result["a2"]), expanded=False)
        with st.expander("A3 · Validación contra el histórico", expanded=True):
            st.json(jsonable(result["a3"]), expanded=False)
        with st.expander("A4 · Reglas operativas ejecutables", expanded=True):
            st.json(jsonable(result["a4"]), expanded=False)
        st.download_button(
            "Descargar trazabilidad JSON",
            json.dumps({key: [jsonable(x) for x in value] if key == "a1" else jsonable(value) for key, value in result.items()}, ensure_ascii=False, indent=2),
            "trazabilidad_pipeline.json",
            "application/json",
        )

with tab_cert:
    if "pipeline_result" not in st.session_state:
        st.info("Aquí aparecerán las métricas del backtesting al terminar la ejecución.")
    else:
        certification = st.session_state["pipeline_result"]["a5"]
        if not certification.results:
            st.warning("A4 no generó reglas: no hay una hipótesis validada para certificar.")
        for item in certification.results:
            st.subheader(f"{item.rule_name} · {'✅ Certificada' if item.certified else '⚠️ No certificada'}")
            c1, c2, c3, c4 = st.columns(4)
            with c1: metric("Tasa de detección", f"{item.detection_rate:.1%}")
            with c2: metric("Falsos positivos", f"{item.false_positive_rate:.1%}")
            with c3: metric("Impacto evitado", f"${item.impact_avoided:,.0f} CLP")
            with c4: metric("Transacciones detectadas", str(item.transactions_detected))
            st.bar_chart({"Verdaderos positivos": item.true_positives, "Falsos positivos": item.false_positives, "Falsos negativos": item.false_negatives})
            st.caption(item.certification_reason)
            st.json(jsonable(item), expanded=False)
