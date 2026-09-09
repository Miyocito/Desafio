from __future__ import annotations

import csv
from datetime import datetime

from dotenv import load_dotenv

from agents.a3_hypothesis_validator import A3HypothesisValidator
from models.schemas import HipotesisA2, TransaccionHistorica


def load_transactions(path: str) -> list[TransaccionHistorica]:
    transactions: list[TransaccionHistorica] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
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
    load_dotenv()

    agent = A3HypothesisValidator()
    transactions = load_transactions("data/sample_transactions.csv")

    hypothesis_1 = HipotesisA2(
        pattern_id="PAT-001",
        hypothesis="Posible concentración de vishing asociado a cargos no reconocidos en comercios de tecnología.",
        indicators={
            "modus_operandi": ["cargo no reconocido y vishing"],
            "canal": ["telefono"],
            "comercio_categoria": ["tecnologia"],
        },
        confidence=0.87,
    )

    hypothesis_2 = HipotesisA2(
        pattern_id="PAT-002",
        hypothesis="Posible fraude de reclamos en comercios retail.",
        indicators={
            "modus_operandi": ["cargo no reconocido"],
            "canal": ["web"],
            "comercio_categoria": ["retail"],
        },
        confidence=0.62,
    )

    result_single = agent.validate_hypothesis(hypothesis_1, transactions)
    print("=== VALIDACIÓN ÚNICA ===")
    print(result_single.model_dump_json(indent=2, exclude_none=False))

    result_many = agent.validate_hypotheses([hypothesis_1, hypothesis_2], transactions)
    print("\n=== VALIDACIÓN MÚLTIPLE ===")
    print(result_many.model_dump_json(indent=2, exclude_none=False))


if __name__ == "__main__":
    main()