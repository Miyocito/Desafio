from __future__ import annotations

import json
from datetime import datetime, timedelta

from dotenv import load_dotenv

from agents.a1_analyst import A1Analyst
from agents.a2_pattern_investigator import A2PatternInvestigator
from models.schemas import CasoA1


def main() -> None:
    load_dotenv()

    a1 = A1Analyst()
    a2 = A2PatternInvestigator()

    now = datetime.now()
    transcripts = [
        (
            "CALL-001",
            now,
            "Hola, quiero desconocer una compra de $450.000 realizada ayer en TechStore. "
            "Yo nunca hice esa compra. Además, recibí una llamada donde me solicitaron "
            "realizar una transferencia para recuperar el dinero.",
        ),
        (
            "CALL-002",
            now - timedelta(minutes=5),
            "Me llamaron desde un supuesto banco y me indicaron validar un código para una compra no reconocida en TechStore.",
        ),
        (
            "CALL-003",
            now - timedelta(minutes=10),
            "Recibí una llamada de soporte y me dijeron que debía transferir dinero para recuperar una compra no reconocida en TechStore.",
        ),
        (
            "CALL-004",
            now - timedelta(minutes=15),
            "Otro caso similar: llamada telefónica, compra no reconocida y solicitud de transferencia en TechStore.",
        ),
        (
            "CALL-005",
            now - timedelta(minutes=20),
            "Me contactaron por teléfono y me pidieron un OTP para resolver una compra no reconocida en TechStore por $470.000.",
        ),
    ]

    print("=== ENTRADA ORIGINAL ===")
    print(json.dumps([
        {"case_id": case_id, "timestamp": timestamp.isoformat(), "transcript": transcript}
        for case_id, timestamp, transcript in transcripts
    ], indent=2, ensure_ascii=False))

    print("\n=== SALIDA A1 POR CASO ===")
    a1_results = []
    for case_id, timestamp, transcript in transcripts:
        result_a1 = a1.process_case(case_id=case_id, timestamp=timestamp, transcript=transcript)
        a1_results.append(result_a1)
        print(f"\n--- {case_id} ---")
        print(result_a1.model_dump_json(indent=2, exclude_none=False))

    cases_a2 = [CasoA1.model_validate(item.model_dump()) for item in a1_results]
    result_a2 = a2.process_cases(cases_a2)

    print("\n=== SALIDA A2 ===")
    print(result_a2.model_dump_json(indent=2, exclude_none=False))


if __name__ == "__main__":
    main()
