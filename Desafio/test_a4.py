from __future__ import annotations

from datetime import datetime

from models.schemas import ResultadoValidacion
from agents.a4_rule_generator import A4RuleGenerator


def main() -> None:
    agent = A4RuleGenerator()

    validation_1 = ResultadoValidacion(
        pattern_id="PAT-001",
        hypothesis="Posible concentración de vishing asociado a cargos no reconocidos en comercios de tecnología.",
        indicators={
            "modus_operandi": ["cargo no reconocido y vishing"],
            "canal": ["telefono"],
            "comercio_categoria": ["tecnologia"],
            "cases": 120,
            "confidence": 0.87,
        },
        validated=True,
        transactions_analyzed=1000,
        matching_transactions=120,
        recurrence_rate=0.12,
        transaction_volume=5400000,
        estimated_financial_cost=4100000,
        validation_reason="La hipótesis supera los umbrales mínimos establecidos.",
    )

    validation_2 = ResultadoValidacion(
        pattern_id="PAT-002",
        hypothesis="Posible fraude de reclamos en comercios retail.",
        indicators={
            "modus_operandi": ["cargo no reconocido"],
            "canal": ["web"],
            "comercio_categoria": ["retail"],
            "cases": 12,
            "confidence": 0.61,
        },
        validated=False,
        transactions_analyzed=1000,
        matching_transactions=12,
        recurrence_rate=0.012,
        transaction_volume=880000,
        estimated_financial_cost=220000,
        validation_reason="La hipótesis no supera los umbrales mínimos.",
    )

    rule = agent.generate_rule(validation_1)
    print("=== REGLA ÚNICA ===")
    print(rule.model_dump_json(indent=2, exclude_none=False))

    try:
        agent.generate_rule(validation_2)
    except Exception as exc:
        print("\n=== HIPÓTESIS NO VALIDADA ===")
        print(str(exc))

    batch_result = agent.generate_rules([validation_1, validation_2])
    print("\n=== REGLAS EN LOTE ===")
    print(batch_result.model_dump_json(indent=2, exclude_none=False))


if __name__ == "__main__":
    main()
