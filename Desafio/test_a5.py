from __future__ import annotations

import csv
from pathlib import Path

from agents.a5_rule_certifier import A5RuleCertifier
from models.schemas import ReglaAccion, ReglaCondicion, ReglaFraude, TransaccionHistorica


DATASET_PATH = Path("data/sample_transactions.csv")


def load_transactions(path: Path) -> list[TransaccionHistorica]:
    transactions: list[TransaccionHistorica] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            transactions.append(
                TransaccionHistorica.model_validate(
                    {
                        "transaction_id": row["transaction_id"],
                        "timestamp": row["timestamp"],
                        "monto": row["monto"],
                        "moneda": row.get("moneda") or None,
                        "comercio_nombre": row.get("comercio_nombre") or None,
                        "comercio_categoria": row.get("comercio_categoria") or None,
                        "canal": row.get("canal") or None,
                        "ciudad": row.get("ciudad") or None,
                        "pais": row.get("pais") or None,
                        "modus_operandi": row.get("modus_operandi") or None,
                        "fraude_confirmado": row.get("fraude_confirmado", "false").strip().lower() == "true",
                    }
                )
            )
    return transactions


def main() -> None:
    transactions = load_transactions(DATASET_PATH)
    agent = A5RuleCertifier()

    rule_1 = ReglaFraude(
        rule_id="RULE-001",
        name="Vishing Tecnologia",
        description="Detecta posibles casos de vishing en comercios de tecnología.",
        source_pattern_id="PAT-001",
        conditions=[
            ReglaCondicion(field="modus_operandi", operator="equals", value="cargo no reconocido y vishing"),
            ReglaCondicion(field="canal", operator="equals", value="telefono"),
            ReglaCondicion(field="comercio_categoria", operator="equals", value="tecnologia"),
        ],
        logic="AND",
        action=ReglaAccion(type="flag", risk_level="high"),
    )

    rule_2 = ReglaFraude(
        rule_id="RULE-002",
        name="Retail Web",
        description="Detecta posibles casos asociados a retail por canal web.",
        source_pattern_id="PAT-002",
        conditions=[
            ReglaCondicion(field="comercio_categoria", operator="equals", value="retail"),
            ReglaCondicion(field="canal", operator="equals", value="web"),
        ],
        logic="AND",
        action=ReglaAccion(type="flag", risk_level="high"),
    )

    result_single = agent.backtest_rule(rule_1, transactions)
    print("=== BACKTEST ÚNICO ===")
    print(result_single.model_dump_json(indent=2, exclude_none=False))

    print("\n=== VALIDACIÓN DE CAMPO INVÁLIDO ===")
    invalid_rule = ReglaFraude(
        rule_id="RULE-999",
        name="Regla Inválida",
        description="Regla de prueba con campo inexistente.",
        source_pattern_id="PAT-999",
        conditions=[
            ReglaCondicion(field="telefono_cliente", operator="equals", value="123"),
        ],
        logic="AND",
        action=ReglaAccion(type="flag", risk_level="high"),
    )
    try:
        agent.backtest_rule(invalid_rule, transactions)
    except Exception as exc:
        print(str(exc))

    result_many = agent.backtest_rules([rule_1, rule_2], transactions)
    print("\n=== BACKTEST EN LOTE ===")
    print(result_many.model_dump_json(indent=2, exclude_none=False))


if __name__ == "__main__":
    main()
