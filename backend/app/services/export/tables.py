"""Build literal spreadsheet matrices and derived row warnings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any, Literal


Warning = Literal["none", "yellow", "red"]


@dataclass(frozen=True, slots=True)
class ExportTable:
    headers: list[str]
    rows: list[list[str | int]]
    warnings: list[Warning]


_DATE_RE = re.compile(r"^([0-9]{1,2})([/.-])([0-9]{1,2})\2([0-9]{2,4})$")


def _contains_question(value: Any) -> bool:
    if isinstance(value, str):
        return "?" in value
    if isinstance(value, dict):
        return any(_contains_question(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_question(item) for item in value)
    return False


def _read_date(raw: str) -> date | None:
    match = _DATE_RE.fullmatch(raw)
    if match is None:
        return None
    day, _, month, year = match.groups()
    full_year = int(year) if len(year) == 4 else 2000 + int(year)
    try:
        return date(full_year, int(month), int(day))
    except ValueError:
        return None


def build_cartao_table(value: dict[str, Any]) -> ExportTable:
    days = [day for page in value["pages"] for day in page["days"]]
    max_punches = max((len(day["punches"]) for day in days), default=0)
    pair_count = (max_punches + 1) // 2
    headers = ["Data"]
    for pair in range(1, pair_count + 1):
        headers.extend((f"Entrada {pair}", f"Saída {pair}"))

    rows: list[list[str | int]] = []
    warnings: list[Warning] = []
    previous_legible: date | None = None
    punch_columns = pair_count * 2
    for day in days:
        # The spreadsheet is the normalized operational view. The literal
        # reading remains available in JSON as time_raw for audit/review.
        times = [punch["time_hhmm"] for punch in day["punches"]]
        rows.append([day["date_raw"], *times, *([""] * (punch_columns - len(times)))])

        current = _read_date(day["date_raw"])
        non_sequential = (
            current is not None
            and previous_legible is not None
            and current != previous_legible + timedelta(days=1)
        )
        yellow = len(day["punches"]) % 2 != 0 or _contains_question(day)
        warnings.append("red" if non_sequential else "yellow" if yellow else "none")
        if current is not None:
            previous_legible = current

    return ExportTable(headers, rows, warnings)


def _read_competence(page: dict[str, Any]) -> tuple[int, int] | None:
    year = page["year"]
    month = page["month"]
    if "?" in year or "?" in month or not year.isdigit() or not month.isdigit():
        return None
    numeric_month = int(month)
    if len(year) != 4 or not 1 <= numeric_month <= 12:
        return None
    return int(year), numeric_month


def _next_competence(competence: tuple[int, int]) -> tuple[int, int]:
    year, month = competence
    return (year + 1, 1) if month == 12 else (year, month + 1)


def build_holerite_table(value: dict[str, Any]) -> ExportTable:
    labels: list[str] = []
    seen_labels: set[str] = set()
    for page in value["pages"]:
        for field in page["fields"]:
            label = field["label"]
            if label not in seen_labels:
                seen_labels.add(label)
                labels.append(label)

    headers = ["Pág.", "Mês", "Ano", *labels]
    rows: list[list[str | int]] = []
    warnings: list[Warning] = []
    previous_legible: tuple[int, int] | None = None
    for page in value["pages"]:
        field_values: dict[str, str] = {}
        for field in page["fields"]:
            field_values.setdefault(field["label"], field["value"])
        rows.append(
            [
                page["page"],
                page["month"],
                page["year"],
                *(field_values.get(label, "") for label in labels),
            ]
        )

        current = _read_competence(page)
        non_sequential = (
            current is not None
            and previous_legible is not None
            and current != _next_competence(previous_legible)
        )
        empty = not page["fields"] and not page["bases"]
        yellow = empty or _contains_question(page)
        warnings.append("red" if non_sequential else "yellow" if yellow else "none")
        if current is not None:
            previous_legible = current

    return ExportTable(headers, rows, warnings)


def build_table(tipo: str, value: dict[str, Any]) -> ExportTable:
    if tipo == "cartao-ponto":
        return build_cartao_table(value)
    if tipo == "holerite":
        return build_holerite_table(value)
    raise ValueError("Tipo de transcrição desconhecido")
