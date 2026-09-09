from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from dotenv import load_dotenv

from models.schemas import HipotesisA2, ResultadoA3, ResultadoValidacion, TransaccionHistorica


load_dotenv()


class A3HypothesisValidator:
    def __init__(
        self,
        minimum_matching_transactions: int = 3,
        minimum_recurrence_rate: float = 0.01,
    ) -> None:
        self.minimum_matching_transactions = minimum_matching_transactions
        self.minimum_recurrence_rate = minimum_recurrence_rate

    @staticmethod
    def _normalize(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned if cleaned else None

    @staticmethod
    def _normalize_many(value: str | list[str] | int | float | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        if isinstance(value, (int, float)):
            return [str(value)]
        text = str(value).strip().lower()
        return [text] if text else []

    @staticmethod
    def _bucket_amount(amount: float) -> str:
        if amount < 50_000:
            return "0-49999"
        if amount < 200_000:
            return "50000-199999"
        if amount < 500_000:
            return "200000-499999"
        if amount < 1_000_000:
            return "500000-999999"
        return "1000000+"

    @staticmethod
    def load_transactions_from_csv(csv_path: str | Path) -> list[TransaccionHistorica]:
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontró el archivo histórico: {path}")

        transactions: list[TransaccionHistorica] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if str(row.get("timestamp", "")).strip().lower() == "timestamp" or str(row.get("monto", "")).strip().lower() == "monto":
                    continue
                transactions.append(
                    TransaccionHistorica.model_validate(
                        {
                            "transaction_id": row.get("transaction_id"),
                            "timestamp": row.get("timestamp"),
                            "monto": row.get("monto"),
                            "moneda": row.get("moneda") or None,
                            "comercio_nombre": row.get("comercio_nombre") or None,
                            "comercio_categoria": row.get("comercio_categoria") or None,
                            "canal": row.get("canal") or None,
                            "ciudad": row.get("ciudad") or None,
                            "pais": row.get("pais") or None,
                            "modus_operandi": row.get("modus_operandi") or None,
                            "fraude_confirmado": str(row.get("fraude_confirmado", "false")).strip().lower() == "true",
                        }
                    )
                )
        return transactions

    def _match_field(self, transaction_value: str | None, indicator_value: str | list[str] | int | float | None) -> bool:
        if indicator_value is None:
            return True

        transaction_norm = self._normalize(transaction_value)
        if transaction_norm is None:
            return False

        candidates = self._normalize_many(indicator_value)
        if not candidates:
            return True

        return transaction_norm in candidates

    def _is_transaction_match(self, transaction: TransaccionHistorica, hypothesis: HipotesisA2) -> bool:
        indicators = hypothesis.indicators or {}

        field_map = {
            "modus_operandi": transaction.modus_operandi,
            "canal": transaction.canal,
            "canal_fraude": transaction.canal,
            "comercio_categoria": transaction.comercio_categoria,
            "categoria_comercio": transaction.comercio_categoria,
            "comercio": transaction.comercio_nombre,
            "comercio_nombre": transaction.comercio_nombre,
            "pais": transaction.pais,
            "ciudad": transaction.ciudad,
            "rango_monto": transaction.monto,
        }

        for key, indicator_value in indicators.items():
            if indicator_value is None:
                continue

            if key in {"cases", "matching_transactions"}:
                continue

            if key not in field_map:
                continue

            transaction_value = field_map.get(key)
            if transaction_value is None:
                return False

            if key == "rango_monto":
                bucket = self._bucket_amount(float(transaction_value))
                if bucket not in self._normalize_many(indicator_value):
                    return False
                continue

            if not self._match_field(str(transaction_value), indicator_value):
                return False

        return True

    def validate_hypothesis(
        self,
        hypothesis: HipotesisA2,
        transactions: list[TransaccionHistorica],
    ) -> ResultadoValidacion:
        validated_hypothesis = HipotesisA2.model_validate(hypothesis.model_dump() if hasattr(hypothesis, "model_dump") else hypothesis)
        validated_transactions = [
            TransaccionHistorica.model_validate(tx.model_dump() if hasattr(tx, "model_dump") else tx)
            for tx in transactions
        ]

        matches = [tx for tx in validated_transactions if self._is_transaction_match(tx, validated_hypothesis)]
        matching_transactions = len(matches)
        transactions_analyzed = len(validated_transactions)
        recurrence_rate = (
            matching_transactions / transactions_analyzed if transactions_analyzed > 0 else 0.0
        )
        transaction_volume = float(sum(tx.monto for tx in matches))
        estimated_financial_cost = float(sum(tx.monto for tx in matches if tx.fraude_confirmado))

        validated = (
            matching_transactions >= self.minimum_matching_transactions
            and recurrence_rate >= self.minimum_recurrence_rate
        )

        if validated:
            validation_reason = (
                "La hipótesis supera los umbrales mínimos de recurrencia y cantidad de transacciones coincidentes."
            )
        else:
            validation_reason = (
                "La hipótesis no alcanza los umbrales mínimos de validación definidos para coincidencias y recurrencia."
            )

        try:
            return ResultadoValidacion(
                pattern_id=validated_hypothesis.pattern_id,
                hypothesis=validated_hypothesis.hypothesis,
                indicators=validated_hypothesis.indicators,
                validated=validated,
                transactions_analyzed=transactions_analyzed,
                matching_transactions=matching_transactions,
                recurrence_rate=recurrence_rate,
                transaction_volume=transaction_volume,
                estimated_financial_cost=estimated_financial_cost,
                validation_reason=validation_reason,
            )
        except Exception as exc:
            raise ValueError(f"La validación calculada no cumple el esquema ResultadoValidacion: {exc}") from exc

    def validate_hypotheses(
        self,
        hypotheses: list[HipotesisA2],
        transactions: list[TransaccionHistorica],
    ) -> ResultadoA3:
        validated_hypotheses = [
            HipotesisA2.model_validate(h.model_dump() if hasattr(h, "model_dump") else h)
            for h in hypotheses
        ]
        validated_transactions = [
            TransaccionHistorica.model_validate(tx.model_dump() if hasattr(tx, "model_dump") else tx)
            for tx in transactions
        ]

        results = [self.validate_hypothesis(hypothesis, validated_transactions) for hypothesis in validated_hypotheses]
        analysis_timestamp = datetime.now()
        analysis_id = f"A3-{analysis_timestamp.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8].upper()}"

        try:
            return ResultadoA3(
                analysis_id=analysis_id,
                timestamp=analysis_timestamp,
                patterns_validated=sum(1 for item in results if item.validated),
                results=results,
            )
        except Exception as exc:
            raise ValueError(f"La salida de A3 no cumple el esquema ResultadoA3: {exc}") from exc
