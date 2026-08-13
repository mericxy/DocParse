"""Pydantic models for both immutable JSON contracts and API responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Punch(ContractModel):
    kind: Literal["IN", "OUT"]
    time_raw: str
    time_hhmm: str


class Day(ContractModel):
    date_raw: str
    punches: list[Punch]


class CartaoPontoPage(ContractModel):
    page: int
    days: list[Day]


class CartaoPontoValue(ContractModel):
    pages: list[CartaoPontoPage]


class HoleriteField(ContractModel):
    code: str
    label: str
    reference: str
    value: str


class HoleriteBase(ContractModel):
    label: str
    value: str


class HoleritePage(ContractModel):
    page: int
    year: str
    month: str
    fields: list[HoleriteField]
    bases: list[HoleriteBase]


class HoleriteValue(ContractModel):
    pages: list[HoleritePage]


TranscriptionValue = CartaoPontoValue | HoleriteValue


class TranscriptionCreated(ContractModel):
    id: str


class TranscriptionResponse(ContractModel):
    id: str
    tipo: Literal["cartao-ponto", "holerite"]
    status: Literal["processando", "concluido", "erro"]
    erro: str | None
    value: TranscriptionValue | None


class ValueUpdate(ContractModel):
    value: dict[str, Any]


_VALUE_ADAPTERS = {
    "cartao-ponto": TypeAdapter(CartaoPontoValue),
    "holerite": TypeAdapter(HoleriteValue),
}


def validate_transcription_value(tipo: str, value: Any) -> dict[str, Any]:
    """Validate and return a JSON-ready value for the persisted document type."""

    adapter = _VALUE_ADAPTERS.get(tipo)
    if adapter is None:
        raise ValueError("Tipo de transcrição desconhecido")
    validated = adapter.validate_python(value)
    return validated.model_dump(mode="json")
