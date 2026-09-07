from __future__ import annotations

import json
from datetime import datetime

from dotenv import load_dotenv

from agents.a1_analyst import A1Analyst


def main() -> None:
    load_dotenv()

    agent = A1Analyst()

    transcript = (
        "Hola, quiero desconocer una compra de $450.000 realizada ayer en TechStore. "
        "Yo nunca hice esa compra. Además, recibí una llamada donde me solicitaron "
        "realizar una transferencia para recuperar el dinero."
    )

    result = agent.process_case(
        case_id="CALL-001",
        timestamp=datetime.now(),
        transcript=transcript,
    )

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
