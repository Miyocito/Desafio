from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from models.schemas import ReglaAccion, ReglaCondicion, ReglaFraude, ResultadoA4, ResultadoValidacion


class A4RuleGenerator:
    def __init__(self) -> None:
        self._rule_counter = 0

    @staticmethod
    def _normalize_text(value: str) -> str:
        cleaned = " ".join(value.strip().split())
        return cleaned

    @staticmethod
    def _is_usable_indicator_value(value: object) -> bool:
        return value is not None and value != [] and value != ""

    def _next_rule_id(self) -> str:
        self._rule_counter += 1
        return f"RULE-{self._rule_counter:03d}"

    def _convert_indicator_to_condition(self, field: str, value: str | list[str] | int | float | None) -> ReglaCondicion | None:
        if value is None:
            return None

        if field in {"cases", "confidence", "matching_transactions", "recurrence_rate", "transaction_volume", "estimated_financial_cost"}:
            return None

        field_aliases = {
            "comercio": "comercio_nombre",
            "categoria_comercio": "comercio_categoria",
            "canal_fraude": "canal",
        }
        target_field = field_aliases.get(field, field)

        if isinstance(value, list):
            cleaned_values = [str(item).strip() for item in value if str(item).strip()]
            if not cleaned_values:
                return None
            if len(cleaned_values) == 1:
                return ReglaCondicion(field=target_field, operator="equals", value=cleaned_values[0])
            return ReglaCondicion(field=target_field, operator="in", value=cleaned_values)

        if isinstance(value, bool):
            return ReglaCondicion(field=target_field, operator="equals", value=value)

        if isinstance(value, (int, float)):
            return ReglaCondicion(field=target_field, operator="equals", value=value)

        text = str(value).strip()
        if not text:
            return None
        return ReglaCondicion(field=target_field, operator="equals", value=text)

    @staticmethod
    def _fraud_terms(value: str | list[str] | int | float | None) -> list[str]:
        """Construye una firma estable para variantes textuales del fraude."""
        if value is None:
            return []
        text = " ".join(str(item) for item in value) if isinstance(value, list) else str(value)
        normalized = text.lower()
        vocabulary = {
            "vishing": "vishing",
            "llamada": "llamada",
            "telefono": "llamada",
            "transfer": "transferencia",
            "otp": "otp",
            "codigo": "codigo",
            "código": "codigo",
            "cargo no reconocido": "cargo no reconocido",
            "compra no reconocida": "compra no reconocida",
            "soporte": "soporte",
        }
        terms = list(dict.fromkeys(term for hint, term in vocabulary.items() if hint in normalized))
        if not terms:
            return []
        # Taxonomía de una misma familia: las transcripciones pueden describir
        # la llamada, la transferencia, el OTP o el falso soporte. A5 decide
        # si esta expansión conserva precisión suficiente en el histórico.
        return [
            "vishing",
            "llamada",
            "transferencia",
            "otp",
            "codigo",
            "cargo no reconocido",
            "compra no reconocida",
            "soporte",
        ]

    def _build_conditions(self, indicators: dict[str, str | list[str] | int | float | None]) -> list[ReglaCondicion]:
        conditions: list[ReglaCondicion] = []
        modus_terms = self._fraud_terms(indicators.get("modus_operandi"))
        has_semantic_signature = bool(modus_terms) and bool(
            indicators.get("canal") or indicators.get("canal_fraude")
        )
        for field, value in indicators.items():
            if field == "modus_operandi" and modus_terms:
                conditions.append(
                    ReglaCondicion(field="modus_operandi", operator="contains_any", value=modus_terms)
                )
                continue
            # Comercio/categoría son contexto; la combinación canal + firma
            # semántica es más estable ante variantes del mismo ataque.
            if has_semantic_signature and field in {
                "comercio_categoria", "categoria_comercio", "comercio", "comercio_nombre", "rango_monto"
            }:
                continue
            condition = self._convert_indicator_to_condition(field, value)
            if condition is not None:
                conditions.append(condition)
        return conditions

    def _build_rule_name(self, indicators: dict[str, str | list[str] | int | float | None]) -> str:
        parts: list[str] = []

        modus = indicators.get("modus_operandi")
        canal = indicators.get("canal") or indicators.get("canal_fraude")
        categoria = indicators.get("comercio_categoria") or indicators.get("categoria_comercio")
        comercio = indicators.get("comercio") or indicators.get("comercio_nombre")

        def add_part(value: object) -> None:
            if isinstance(value, list) and value:
                candidate = str(value[0]).strip()
                if candidate:
                    parts.append(candidate)
            elif isinstance(value, str) and value.strip():
                parts.append(value.strip())

        add_part(modus)
        add_part(canal)
        add_part(categoria)
        add_part(comercio)

        if not parts:
            return "Fraude Detectado"

        cleaned = []
        for part in parts[:3]:
            normalized = self._normalize_text(part)
            normalized = normalized.replace(" y ", " ")
            cleaned.append(normalized.title())
        return " ".join(cleaned)

    def _build_description(self, validation: ResultadoValidacion) -> str:
        indicators = validation.indicators
        components: list[str] = []

        modus = indicators.get("modus_operandi")
        canal = indicators.get("canal") or indicators.get("canal_fraude")
        categoria = indicators.get("comercio_categoria") or indicators.get("categoria_comercio")
        comercio = indicators.get("comercio") or indicators.get("comercio_nombre")

        if modus:
            components.append(f"{modus if isinstance(modus, str) else modus[0]}")
        if canal:
            components.append(f"canal {canal if isinstance(canal, str) else canal[0]}")
        if categoria:
            components.append(f"comercios de {categoria if isinstance(categoria, str) else categoria[0]}")
        if comercio:
            components.append(f"comercio {comercio if isinstance(comercio, str) else comercio[0]}")

        if not components:
            components.append("patrón validado por A3")

        return (
            "Detecta transacciones asociadas a "
            + ", ".join(components)
            + "."
        )

    def generate_rule(self, validation: ResultadoValidacion) -> ReglaFraude:
        validated_validation = ResultadoValidacion.model_validate(
            validation.model_dump() if hasattr(validation, "model_dump") else validation
        )

        if not validated_validation.validated:
            raise ValueError("No se puede generar una regla para una hipótesis no validada.")

        conditions = self._build_conditions(validated_validation.indicators)
        if not conditions:
            raise ValueError("No se encontraron indicadores utilizables para construir la regla.")

        rule = ReglaFraude(
            rule_id=self._next_rule_id(),
            name=self._build_rule_name(validated_validation.indicators),
            description=self._build_description(validated_validation),
            source_pattern_id=validated_validation.pattern_id,
            conditions=conditions,
            logic="AND",
            action=ReglaAccion(type="flag", risk_level="high"),
        )
        return ReglaFraude.model_validate(rule.model_dump())

    def generate_rules(self, validations: list[ResultadoValidacion]) -> ResultadoA4:
        rules: list[ReglaFraude] = []
        for validation in validations:
            validated = ResultadoValidacion.model_validate(
                validation.model_dump() if hasattr(validation, "model_dump") else validation
            )
            if not validated.validated:
                continue
            rules.append(self.generate_rule(validated))

        generation_timestamp = datetime.now()
        generation_id = f"A4-{generation_timestamp.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}"

        return ResultadoA4(
            generation_id=generation_id,
            timestamp=generation_timestamp,
            rules_generated=len(rules),
            rules=rules,
        )
