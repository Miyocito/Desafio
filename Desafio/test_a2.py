from __future__ import annotations

import json
from datetime import datetime, timedelta

from dotenv import load_dotenv

from agents.a2_pattern_investigator import A2PatternInvestigator
from models.schemas import CasoA1, UbicacionGeografica


def main() -> None:
    load_dotenv()

    agent = A2PatternInvestigator()

    now = datetime.now()
    cases = [
        CasoA1(
            case_id="CALL-001",
            timestamp=now,
            transcript_text="Llamada fraudulenta: me pidieron validar un código OTP para una compra no reconocida en TechStore.",
            monto_reportado=450000,
            moneda="CLP",
            comercio_nombre="TechStore",
            comercio_categoria="tecnologia",
            modus_operandi="cargo no reconocido y vishing",
            canal_fraude="telefono",
            ubicacion_geografica=UbicacionGeografica(ciudad=None, pais=None),
            nivel_confianza_extraccion=0.95,
        ),
        CasoA1(
            case_id="CALL-002",
            timestamp=now - timedelta(minutes=5),
            transcript_text="Llamada similar sobre cargo no reconocido en TechStore y solicitud de transferencia para recuperar el dinero.",
            monto_reportado=470000,
            moneda="CLP",
            comercio_nombre="TechStore",
            comercio_categoria="tecnologia",
            modus_operandi="cargo no reconocido y vishing",
            canal_fraude="telefono",
            ubicacion_geografica=UbicacionGeografica(ciudad=None, pais=None),
            nivel_confianza_extraccion=0.94,
        ),
        CasoA1(
            case_id="CALL-003",
            timestamp=now - timedelta(minutes=10),
            transcript_text="Me llamaron desde un supuesto banco y me pidieron un código para revertir una compra en TechStore.",
            monto_reportado=430000,
            moneda="CLP",
            comercio_nombre="TechStore",
            comercio_categoria="tecnologia",
            modus_operandi="cargo no reconocido y vishing",
            canal_fraude="telefono",
            ubicacion_geografica=UbicacionGeografica(ciudad=None, pais=None),
            nivel_confianza_extraccion=0.93,
        ),
        CasoA1(
            case_id="CALL-004",
            timestamp=now - timedelta(minutes=15),
            transcript_text="Se reporta una compra no reconocida en TechStore tras una llamada telefónica de supuesta verificación.",
            monto_reportado=460000,
            moneda="CLP",
            comercio_nombre="TechStore",
            comercio_categoria="tecnologia",
            modus_operandi="cargo no reconocido y vishing",
            canal_fraude="telefono",
            ubicacion_geografica=UbicacionGeografica(ciudad=None, pais=None),
            nivel_confianza_extraccion=0.96,
        ),
        CasoA1(
            case_id="CALL-005",
            timestamp=now - timedelta(minutes=20),
            transcript_text="Otra llamada por una compra no reconocida en TechStore y una instrucción para transferir fondos.",
            monto_reportado=440000,
            moneda="CLP",
            comercio_nombre="TechStore",
            comercio_categoria="tecnologia",
            modus_operandi="cargo no reconocido y vishing",
            canal_fraude="telefono",
            ubicacion_geografica=UbicacionGeografica(ciudad=None, pais=None),
            nivel_confianza_extraccion=0.95,
        ),
    ]

    result = agent.process_cases(cases)
    print(result.model_dump_json(indent=2, exclude_none=False))


if __name__ == "__main__":
    main()
