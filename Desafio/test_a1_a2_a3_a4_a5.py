from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agents.a1_analyst import A1Analyst
from agents.a2_pattern_investigator import A2PatternInvestigator
from agents.a3_hypothesis_validator import A3HypothesisValidator
from agents.a4_rule_generator import A4RuleGenerator
from agents.a5_rule_certifier import A5RuleCertifier
from models.schemas import CasoA1


INPUT_CASES_CSV = Path("data/a1_input_cases.csv")
HISTORICAL_CSV = Path("data/historical_transactions.csv")


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def main() -> None:
    load_dotenv()

    a1 = A1Analyst()
    a2 = A2PatternInvestigator()
    a3 = A3HypothesisValidator()
    a4 = A4RuleGenerator()
    a5 = A5RuleCertifier()

    input_cases = load_csv_rows(INPUT_CASES_CSV)
    print_json_block("ENTRADA A1", input_cases)

    a1_results = []
    print("\n=== SALIDA A1 POR CASO ===")
    for row in input_cases:
        result_a1 = a1.process_case(
            case_id=row["case_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            transcript=row["transcript"],
        )
        a1_results.append(result_a1)
        print(f"\n--- {row['case_id']} ---")
        print(result_a1.model_dump_json(indent=2, exclude_none=False))

    run_prefix = datetime.now().strftime("RUN%Y%m%d%H%M%S")
    append_transactions_to_history(HISTORICAL_CSV, a1_results, run_prefix)
    print_json_block(
        "HISTÓRICO ACUMULADO ACTUALIZADO",
        {"historical_csv": str(HISTORICAL_CSV), "new_rows_appended": len(a1_results)},
    )

    a1_as_caso_a1 = [CasoA1.model_validate(item.model_dump()) for item in a1_results]
    result_a2 = a2.process_cases(a1_as_caso_a1)
    print_json_block("SALIDA A2", result_a2.model_dump(mode="json"))

    transactions_a3 = a3.load_transactions_from_csv(HISTORICAL_CSV)
    if not result_a2.patterns:
        print("\nNo se generaron hipótesis desde A2, por lo tanto A3-A5 no tienen patrones que procesar.")
        return

    print("\n=== SALIDA A3 POR HIPÓTESIS ===")
    validations = []
    for pattern in result_a2.patterns:
        validation = a3.validate_hypothesis(pattern, transactions_a3)
        validations.append(validation)
        print(f"\n--- {pattern.pattern_id} ---")
        print(validation.model_dump_json(indent=2, exclude_none=False))

    result_a3 = a3.validate_hypotheses(result_a2.patterns, transactions_a3)
    print_json_block("SALIDA A3 AGREGADA", result_a3.model_dump(mode="json"))

    result_a4 = a4.generate_rules(validations)
    print_json_block("SALIDA A4", result_a4.model_dump(mode="json"))

    transactions_a5 = load_transactions_for_a5(HISTORICAL_CSV)
    print_json_block(
        "DATASET HISTÓRICO PARA A5",
        {"historical_csv": str(HISTORICAL_CSV), "rows": len(transactions_a5)},
    )

    print("\n=== SALIDA A5 POR REGLA ===")
    for rule in result_a4.rules:
        backtest = a5.backtest_rule(rule, transactions_a5)
        print(f"\n--- {rule.rule_id} ---")
        print(backtest.model_dump_json(indent=2, exclude_none=False))

    result_a5 = a5.backtest_rules(result_a4.rules, transactions_a5)
    print_json_block("SALIDA A5 AGREGADA", result_a5.model_dump(mode="json"))


if __name__ == "__main__":
    main()
