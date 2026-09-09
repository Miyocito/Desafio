from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agents.a1_analyst import A1Analyst
from agents.a2_pattern_investigator import A2PatternInvestigator
from agents.a3_hypothesis_validator import A3HypothesisValidator
from agents.a4_rule_generator import A4RuleGenerator
from agents.a5_rule_certifier import A5RuleCertifier
from models.schemas import CasoA1, HipotesisA2, ReglaAccion, ReglaCondicion, ReglaFraude


INPUT_CASES_CSV = Path("data/a1_input_cases.csv")
HISTORICAL_CSV = Path("data/historical_transactions.csv")


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: Any


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def check_csv_has_columns(path: Path, required_columns: list[str]) -> CheckResult:
    rows = load_csv_rows(path)
    if not rows:
        return CheckResult(path.name, False, "El CSV no contiene filas de datos.")

    missing = [col for col in required_columns if col not in rows[0]]
    if missing:
        return CheckResult(path.name, False, f"Faltan columnas requeridas: {missing}")

    return CheckResult(path.name, True, {"rows": len(rows), "columns": list(rows[0].keys())})


def instantiate_agents() -> tuple[Any, Any, Any, Any, Any, list[CheckResult]]:
    results: list[CheckResult] = []
    agents: dict[str, Any] = {}

    for name, factory in [
        ("A1", A1Analyst),
        ("A2", A2PatternInvestigator),
        ("A3", A3HypothesisValidator),
        ("A4", A4RuleGenerator),
        ("A5", A5RuleCertifier),
    ]:
        try:
            agents[name] = factory()
            results.append(CheckResult(f"{name}_init", True, "Inicializado correctamente."))
        except Exception as exc:
            agents[name] = None
            results.append(CheckResult(f"{name}_init", False, str(exc)))

    return agents["A1"], agents["A2"], agents["A3"], agents["A4"], agents["A5"], results


def append_transactions_to_history(history_path: Path, a1_results: list, run_prefix: str) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "transaction_id",
        "timestamp",
        "monto",
        "moneda",
        "comercio_nombre",
        "comercio_categoria",
        "canal",
        "ciudad",
        "pais",
        "modus_operandi",
        "fraude_confirmado",
    ]

    existing_rows: list[dict[str, str]] = []
    if history_path.exists():
        existing_rows.extend(load_csv_rows(history_path))

    for index, case in enumerate(a1_results, start=1):
        payload = case.model_dump()
        ubicacion = payload.get("ubicacion_geografica") or {}
        existing_rows.append(
            {
                "transaction_id": f"{run_prefix}-TX-{index:03d}",
                "timestamp": payload["timestamp"].isoformat() if hasattr(payload["timestamp"], "isoformat") else str(payload["timestamp"]),
                "monto": payload.get("monto_reportado") or 0,
                "moneda": payload.get("moneda") or "CLP",
                "comercio_nombre": payload.get("comercio_nombre") or "Desconocido",
                "comercio_categoria": payload.get("comercio_categoria") or "desconocido",
                "canal": payload.get("canal_fraude") or "desconocido",
                "ciudad": ubicacion.get("ciudad") if isinstance(ubicacion, dict) else None,
                "pais": ubicacion.get("pais") if isinstance(ubicacion, dict) else None,
                "modus_operandi": payload.get("modus_operandi") or "desconocido",
                "fraude_confirmado": "true",
            }
        )

    with history_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)


def load_transactions_for_a5(path: Path):
    return A5RuleCertifier.load_transactions_from_csv(path)


def print_json_block(title: str, value) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def run_deterministic_sanity(a3: A3HypothesisValidator, a4: A4RuleGenerator, a5: A5RuleCertifier) -> list[CheckResult]:
    results: list[CheckResult] = []
    transactions = a3.load_transactions_from_csv(HISTORICAL_CSV)

    sanity_hypothesis = HipotesisA2(
        pattern_id="PAT-SANITY-001",
        hypothesis="Posible fraude por telefono asociado a categoria tecnologia y comercios TechStore.",
        indicators={
            "modus_operandi": [
                "cargo no reconocido y vishing",
                "llamada para solicitar transferencia",
                "vishing con validacion de codigo para compra no reconocida",
            ],
            "canal": ["telefono"],
            "comercio_categoria": ["tecnologia", "e-commerce"],
            "comercio": ["TechStore"],
        },
        confidence=0.9,
    )

    validation = a3.validate_hypothesis(sanity_hypothesis, transactions)
    results.append(CheckResult("sanity_A3_validation", validation.validated, validation.model_dump(mode="json")))

    if validation.validated:
        rule = a4.generate_rule(validation)
        results.append(CheckResult("sanity_A4_rule", True, rule.model_dump(mode="json")))
        backtest = a5.backtest_rule(rule, transactions)
        results.append(CheckResult("sanity_A5_backtest", True, backtest.model_dump(mode="json")))
    else:
        results.append(CheckResult("sanity_A4_rule", False, "La hipótesis de sanity no fue validada por A3."))
        results.append(CheckResult("sanity_A5_backtest", False, "No se generó regla para backtesting."))

    return results


def run_end_to_end_if_possible(a1, a2, a3, a4, a5) -> list[CheckResult]:
    results: list[CheckResult] = []

    if a1 is None or a2 is None:
        results.append(CheckResult("pipeline_run", False, "A1/A2 no pudieron inicializarse; se usa sanity check determinístico."))
        return results

    input_rows = load_csv_rows(INPUT_CASES_CSV)
    a1_results = [
        a1.process_case(
            case_id=row["case_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            transcript=row["transcript"],
        )
        for row in input_rows
    ]
    results.append(CheckResult("A1_cases", True, {"processed": len(a1_results)}))

    caso_a1 = [CasoA1.model_validate(item.model_dump()) for item in a1_results]
    a2_result = a2.process_cases(caso_a1)
    results.append(CheckResult("A2_patterns", bool(a2_result.patterns), a2_result.model_dump(mode="json")))

    if not a2_result.patterns:
        results.append(CheckResult("pipeline_run", False, "A2 no generó patrones para continuar con A3-A5."))
        return results

    historical_transactions = a3.load_transactions_from_csv(HISTORICAL_CSV)
    a3_validations = [a3.validate_hypothesis(pattern, historical_transactions) for pattern in a2_result.patterns]
    valid_count = sum(1 for validation in a3_validations if validation.validated)
    results.append(CheckResult("A3_validation", valid_count > 0, {"validated": valid_count, "total": len(a3_validations)}))

    if valid_count == 0:
        results.append(CheckResult("pipeline_run", False, "A3 no validó patrones suficientes para A4."))
        return results

    a4_result = a4.generate_rules(a3_validations)
    results.append(CheckResult("A4_rules", a4_result.rules_generated > 0, a4_result.model_dump(mode="json")))

    transactions_a5 = a5.load_transactions_from_csv(HISTORICAL_CSV)
    if a4_result.rules:
        backtest = a5.backtest_rules(a4_result.rules, transactions_a5)
        results.append(CheckResult("A5_backtesting", True, backtest.model_dump(mode="json")))
    else:
        results.append(CheckResult("A5_backtesting", False, "A4 no generó reglas."))

    return results


def run_integrity_check() -> list[CheckResult]:
    results: list[CheckResult] = []

    if not INPUT_CASES_CSV.exists():
        results.append(CheckResult(INPUT_CASES_CSV.name, False, "No existe el dataset de entrada para A1."))
        return results
    if not HISTORICAL_CSV.exists():
        results.append(CheckResult(HISTORICAL_CSV.name, False, "No existe el histórico acumulado."))
        return results

    results.append(
        check_csv_has_columns(
            INPUT_CASES_CSV,
            ["case_id", "timestamp", "transcript"],
        )
    )
    results.append(
        check_csv_has_columns(
            HISTORICAL_CSV,
            [
                "transaction_id",
                "timestamp",
                "monto",
                "moneda",
                "comercio_nombre",
                "comercio_categoria",
                "canal",
                "ciudad",
                "pais",
                "modus_operandi",
                "fraude_confirmado",
            ],
        )
    )

    a1, a2, a3, a4, a5, init_results = instantiate_agents()
    results.extend(init_results)

    # Intenta el flujo completo cuando las integraciones están disponibles.
    results.extend(run_end_to_end_if_possible(a1, a2, a3, a4, a5))

    # Siempre ejecuta un sanity check determinístico sobre A3-A5.
    if a3 is not None and a4 is not None and a5 is not None:
        results.extend(run_deterministic_sanity(a3, a4, a5))

    return results


def main() -> None:
    load_dotenv()

    results = run_integrity_check()
    payload = {
        "ok": all(item.ok for item in results),
        "results": [
            {"name": item.name, "ok": item.ok, "details": item.details}
            for item in results
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
