"""Layout-aware extraction of payroll slips from the shared PDF model.

The pipeline is deliberately split at the PDF reader boundary: embedded text
and OCR both arrive here as :class:`PdfPage` / :class:`PdfWord`.  Inside the
document-specific extractor, a small dispatcher selects one of the structural
layouts evidenced by the sample documents.  Every layout derives its column
bands from semantic headers; no sample PDF coordinate is used as a rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
import re
from statistics import median
import unicodedata
from typing import Any

from ..pdf.models import BoundingBox, PdfPage, PdfWord
from ..pdf.reader import read_pdf


_LINE_CENTER_TOLERANCE_HEIGHT_FACTOR = 0.45
_LINE_CENTER_TOLERANCE_PAGE_FACTOR = 0.001
_MONEY_RE = re.compile(
    r"^-?(?:[0-9?]{1,3}(?:\.[0-9?]{3})+|[0-9?]+),[0-9?]{2}$"
)
_REFERENCE_NUMBER_RE = re.compile(r"^-?[0-9?]+(?:[.,][0-9?]+)?$")
_CODE_RE = re.compile(r"^/?[A-Za-z0-9?]+$")
_NUMERIC_COMPETENCE_RE = re.compile(
    r"(?<![0-9?])([0-9?]{1,2})/([0-9?]{4})(?![0-9?])"
)
_LEDGER_COMPETENCE_RE = re.compile(
    r"\b([A-Za-zÀ-ÿ?]{3})-([0-9?]{2})\b",
    re.IGNORECASE,
)
_NAMED_COMPETENCE_RE = re.compile(
    r"([A-Za-zÀ-ÿ?]+)\s*/\s*([0-9?]{4})",
    re.IGNORECASE,
)

_PORTUGUESE_MONTHS = {
    "jan": "01",
    "janeiro": "01",
    "fev": "02",
    "fevereiro": "02",
    "mar": "03",
    "marco": "03",
    "abr": "04",
    "abril": "04",
    "mai": "05",
    "maio": "05",
    "jun": "06",
    "junho": "06",
    "jul": "07",
    "julho": "07",
    "ago": "08",
    "agosto": "08",
    "set": "09",
    "setembro": "09",
    "out": "10",
    "outubro": "10",
    "nov": "11",
    "novembro": "11",
    "dez": "12",
    "dezembro": "12",
}


@dataclass(slots=True)
class _Line:
    words: list[PdfWord]
    bbox: BoundingBox


@dataclass(frozen=True, slots=True)
class _FourColumns:
    code_label: float
    label_reference: float
    reference_value: float


@dataclass(frozen=True, slots=True)
class _FiveColumns:
    code_label: float
    label_reference: float
    reference_provents: float
    provents_discounts: float


@dataclass(frozen=True, slots=True)
class _ReceiptColumns:
    label_start: float
    label_reference: float
    reference_value: float
    missing_prefix_tolerance: float


def _semantic_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9?]", "", without_accents.casefold())


def _ordered_words(line: _Line) -> list[PdfWord]:
    # Sorting inside one visual baseline restores left-to-right reading order;
    # output pages and records themselves are never sorted.
    return sorted(line.words, key=lambda word: word.bbox.x0)


def _line_text(line: _Line) -> str:
    return " ".join(word.text for word in _ordered_words(line)).strip()


def _line_semantic(line: _Line) -> str:
    return _semantic_text(_line_text(line))


def _make_lines(page: PdfPage) -> list[_Line]:
    """Group visual baselines using scale derived from the page's own words."""

    if not page.words:
        return []
    median_height = median(word.bbox.y1 - word.bbox.y0 for word in page.words)
    tolerance = max(
        median_height * _LINE_CENTER_TOLERANCE_HEIGHT_FACTOR,
        page.height * _LINE_CENTER_TOLERANCE_PAGE_FACTOR,
    )
    lines: list[_Line] = []
    for word in page.words:
        closest: _Line | None = None
        closest_distance = float("inf")
        for candidate in lines:
            distance = abs(candidate.bbox.center_y - word.bbox.center_y)
            if distance <= tolerance and distance < closest_distance:
                closest = candidate
                closest_distance = distance
        if closest is None:
            lines.append(_Line([word], word.bbox))
            continue
        closest.words.append(word)
        closest.bbox = BoundingBox(
            min(closest.bbox.x0, word.bbox.x0),
            min(closest.bbox.y0, word.bbox.y0),
            max(closest.bbox.x1, word.bbox.x1),
            max(closest.bbox.y1, word.bbox.y1),
        )
    return lines


def _empty_page(page_number: int) -> dict[str, Any]:
    return {"page": page_number, "year": "", "month": "", "fields": [], "bases": []}


def _result_page(
    page_number: int,
    year: str,
    month: str,
    fields: list[dict[str, str]],
    bases: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "page": page_number,
        "year": year,
        "month": month,
        "fields": fields,
        "bases": bases,
    }


def _money(word: PdfWord) -> str | None:
    token = word.text.strip()
    return token if _MONEY_RE.fullmatch(token) else None


def _clean_base_label(words: list[PdfWord]) -> str:
    return " ".join(word.text for word in words).strip().rstrip(":").strip()


def _pairs_ending_in_money(words: list[PdfWord]) -> list[dict[str, str]]:
    """Read repeated ``label ... monetary-value`` pairs from one visual line."""

    pairs: list[dict[str, str]] = []
    label_words: list[PdfWord] = []
    for word in sorted(words, key=lambda item: item.bbox.x0):
        value = _money(word)
        if value is None:
            label_words.append(word)
            continue
        label = _clean_base_label(label_words)
        if label:
            pairs.append({"label": label, "value": value})
        label_words = []
    return pairs


def _normalize_numeric_month(raw_month: str) -> str:
    if "?" in raw_month:
        return raw_month if len(raw_month) == 2 else "??"
    if not raw_month.isdigit():
        return "??"
    month_number = int(raw_month)
    return f"{month_number:02d}" if 1 <= month_number <= 12 else "??"


def _numeric_competence(line: _Line) -> tuple[str, str] | None:
    match = _NUMERIC_COMPETENCE_RE.search(_line_text(line))
    if match is None:
        return None
    month = _normalize_numeric_month(match.group(1))
    year = match.group(2)
    return year, month


def _ledger_competence(line: _Line) -> tuple[str, str] | None:
    match = _LEDGER_COMPETENCE_RE.search(_line_text(line))
    if match is None:
        return None
    month = _PORTUGUESE_MONTHS.get(_semantic_text(match.group(1)), "")
    short_year = match.group(2)
    # This layout explicitly prints a two-digit year. Expanding its documented
    # 20xx convention is deterministic formatting, not inference from adjacent
    # pages or competencies.
    year = f"20{short_year}"
    return year, month


def _named_competence(line: _Line) -> tuple[str, str] | None:
    match = _NAMED_COMPETENCE_RE.search(_line_text(line))
    if match is None:
        return None
    # A named month token is visibly present. If OCR garbled it beyond an exact
    # known spelling, expose character uncertainty instead of fuzzy-matching a
    # likely month or borrowing one from neighbouring pages.
    month = _PORTUGUESE_MONTHS.get(_semantic_text(match.group(1)), "??")
    return match.group(2), month


def _word_with_semantic(line: _Line, token: str) -> PdfWord | None:
    return next(
        (word for word in _ordered_words(line) if _semantic_text(word.text) == token),
        None,
    )


def _boundary(left: PdfWord, right: PdfWord) -> float:
    return (left.bbox.center_x + right.bbox.center_x) / 2


def _three_section_bounds(lines: list[_Line]) -> tuple[float, float] | None:
    """Derive Rendimentos / Descontos / Resultados bands from their header."""

    for line in lines:
        semantic = _line_semantic(line)
        if not all(token in semantic for token in ("rendimentos", "descontos", "resultados")):
            continue
        words = _ordered_words(line)
        gaps = [
            (right.bbox.x0 - left.bbox.x1, index)
            for index, (left, right) in enumerate(zip(words, words[1:]))
        ]
        if len(gaps) < 2:
            continue
        largest = sorted(gaps, reverse=True)[:2]
        split_indexes = sorted(index for _, index in largest)
        first_end, second_end = split_indexes
        groups = (
            words[: first_end + 1],
            words[first_end + 1 : second_end + 1],
            words[second_end + 1 :],
        )
        if not all(groups):
            continue
        if (
            "rendimentos" not in _semantic_text("".join(word.text for word in groups[0]))
            or "descontos" not in _semantic_text("".join(word.text for word in groups[1]))
            or "resultados" not in _semantic_text("".join(word.text for word in groups[2]))
        ):
            continue
        rough_bounds = (
            (groups[0][-1].bbox.x1 + groups[1][0].bbox.x0) / 2,
            (groups[1][-1].bbox.x1 + groups[2][0].bbox.x0) / 2,
        )
        # Section titles are centered, while row content is right-aligned. Find
        # the actual start of the rightmost label/value pairs below the header
        # so a discount value near the title midpoint is not misclassified as
        # a Resultados value.
        result_label_starts: list[float] = []
        for data_line in lines[lines.index(line) + 1 :]:
            data_words = _ordered_words(data_line)
            money_indexes = [index for index, word in enumerate(data_words) if _money(word)]
            if not money_indexes:
                continue
            last_money = money_indexes[-1]
            previous_money = money_indexes[-2] if len(money_indexes) > 1 else -1
            label_words = [
                word
                for word in data_words[previous_money + 1 : last_money]
                if word.bbox.x0 > rough_bounds[1]
            ]
            if label_words:
                result_label_starts.append(label_words[0].bbox.x0)
        return (
            rough_bounds[0],
            min(result_label_starts) if result_label_starts else rough_bounds[1],
        )
    return None


def _zone_words(line: _Line, left: float, right: float) -> list[PdfWord]:
    return [
        word
        for word in _ordered_words(line)
        if left <= word.bbox.center_x < right
    ]


def _ledger_field(words: list[PdfWord]) -> dict[str, str] | None:
    if not words:
        return None
    money_indexes = [index for index, word in enumerate(words) if _money(word)]
    if not money_indexes:
        return None
    value_index = money_indexes[-1]
    value = _money(words[value_index])
    assert value is not None
    prefix = words[:value_index]
    reference = ""
    if len(prefix) >= 2 and _REFERENCE_NUMBER_RE.fullmatch(prefix[-1].text.strip()):
        reference = prefix[-1].text.strip()
        prefix = prefix[:-1]
    # In the Ledger layout, every actual earning/discount row starts with its
    # numeric rubric code. Code-less rows such as REMUNERAÇÃO MÊS and
    # DIAS/HORAS TRAB belong to the block summary, not to the verb table.
    if len(prefix) < 2 or not prefix[0].text.isdigit():
        return None
    code = prefix[0].text
    prefix = prefix[1:]
    label = " ".join(word.text for word in prefix).strip()
    if not label:
        return None
    return {"code": code, "label": label, "reference": reference, "value": value}


def _ledger_base(words: list[PdfWord]) -> dict[str, str] | None:
    pairs = _pairs_ending_in_money(words)
    return pairs[0] if pairs else None


def _parse_ledger_range(
    page: PdfPage,
    lines: list[_Line],
    start: int,
    end: int,
    bounds: tuple[float, float],
    competence: tuple[str, str],
) -> dict[str, Any]:
    first_right, second_right = bounds
    year, month = competence
    fields: list[dict[str, str]] = []
    bases: list[dict[str, str]] = []
    earnings_open = True
    discounts_open = True
    for line in lines[start + 1 : end]:
        if "assinadoeletronicamente" in _line_semantic(line):
            break
        zones = (
            _zone_words(line, 0, first_right),
            _zone_words(line, first_right, second_right),
            _zone_words(line, second_right, page.width),
        )
        for zone_index, words in enumerate(zones):
            semantic = _semantic_text(" ".join(word.text for word in words))
            if zone_index == 0:
                if semantic.startswith(("totrendimentos", "totalrendimentos")):
                    base = _ledger_base(words)
                    if base:
                        bases.append(base)
                    earnings_open = False
                elif earnings_open:
                    field = _ledger_field(words)
                    if field:
                        fields.append(field)
            elif zone_index == 1:
                if semantic.startswith("totaldescontos"):
                    base = _ledger_base(words)
                    if base:
                        bases.append(base)
                    discounts_open = False
                elif discounts_open:
                    field = _ledger_field(words)
                    if field:
                        fields.append(field)
            else:
                base = _ledger_base(words)
                if base:
                    bases.append(base)
    return _result_page(page.number, year, month, fields, bases)


def _parse_ledger(
    page: PdfPage,
    lines: list[_Line],
    inherited_bounds: tuple[float, float] | None = None,
) -> list[dict[str, Any]]:
    bounds = _three_section_bounds(lines) or inherited_bounds
    if bounds is None:
        return []
    anchors = [
        (index, competence)
        for index, line in enumerate(lines)
        if (competence := _ledger_competence(line)) is not None
    ]
    results: list[dict[str, Any]] = []

    # A physical page may begin with the remainder of a block started on the
    # preceding page. We preserve that fragment with an empty competence rather
    # than copying the previous page's month/year, which the contract forbids.
    first_anchor = anchors[0][0] if anchors else len(lines)
    if inherited_bounds is not None and first_anchor > 0:
        orphan = _parse_ledger_range(page, lines, -1, first_anchor, bounds, ("", ""))
        if orphan["fields"] or orphan["bases"]:
            results.append(orphan)

    for anchor_position, (start, (year, month)) in enumerate(anchors):
        end = anchors[anchor_position + 1][0] if anchor_position + 1 < len(anchors) else len(lines)
        if results:
            # In this three-column report the left column can start the next
            # monthly block while a longer discount column from the preceding
            # block still occupies the same visual baseline. Preserve that
            # right-side item with the preceding block instead of dropping the
            # complete anchor line.
            overlap_words = _zone_words(lines[start], bounds[0], bounds[1])
            overlap_semantic = _semantic_text(
                " ".join(word.text for word in overlap_words)
            )
            if overlap_semantic.startswith("totaldescontos"):
                if base := _ledger_base(overlap_words):
                    results[-1]["bases"].append(base)
            elif field := _ledger_field(overlap_words):
                results[-1]["fields"].append(field)
            if base := _ledger_base(_zone_words(lines[start], bounds[1], page.width)):
                results[-1]["bases"].append(base)
        results.append(_parse_ledger_range(page, lines, start, end, bounds, (year, month)))
    return results


def _four_columns_from_header(line: _Line) -> _FourColumns | None:
    code = _word_with_semantic(line, "verba")
    label = _word_with_semantic(line, "nome")
    reference = _word_with_semantic(line, "base")
    value = _word_with_semantic(line, "valor")
    if None in (code, label, reference, value):
        return None
    assert code and label and reference and value
    return _FourColumns(
        _boundary(code, label),
        reference.bbox.x0,
        value.bbox.x0,
    )


def _corporate_field(line: _Line, columns: _FourColumns) -> dict[str, str] | None:
    words = _ordered_words(line)
    code = words[0].text.strip() if words else ""
    if not code or not _CODE_RE.fullmatch(code):
        return None
    label = " ".join(
        word.text
        for word in words[1:]
        if word.bbox.center_x < columns.label_reference
    ).strip()
    reference = " ".join(
        word.text
        for word in words
        if columns.label_reference <= word.bbox.center_x < columns.reference_value
    ).strip()
    value_candidates = [
        value
        for word in words
        if word.bbox.center_x >= columns.reference_value
        if (value := _money(word)) is not None
    ]
    if not label:
        return None
    return {
        "code": code,
        "label": label,
        "reference": reference,
        "value": value_candidates[-1] if value_candidates else "",
    }


def _parse_corporate(page: PdfPage, lines: list[_Line]) -> list[dict[str, Any]]:
    anchors = [
        (index, competence)
        for index, line in enumerate(lines)
        if "mesano" in _line_semantic(line)
        and (competence := _numeric_competence(line)) is not None
    ]
    results: list[dict[str, Any]] = []
    for anchor_position, (start, (year, month)) in enumerate(anchors):
        end = anchors[anchor_position + 1][0] if anchor_position + 1 < len(anchors) else len(lines)
        header_index: int | None = None
        columns: _FourColumns | None = None
        for index in range(start + 1, end):
            candidate = _four_columns_from_header(lines[index])
            if candidate is not None:
                header_index = index
                columns = candidate
                break
        if header_index is None or columns is None:
            results.append(_result_page(page.number, year, month, [], []))
            continue

        fields: list[dict[str, str]] = []
        base_start = end
        for index in range(header_index + 1, end):
            field = _corporate_field(lines[index], columns)
            if field is None:
                base_start = index
                break
            fields.append(field)

        bases: list[dict[str, str]] = []
        for line in lines[base_start:end]:
            semantic = _line_semantic(line)
            if "impresso" in semantic or "assinadoeletronicamente" in semantic:
                break
            bases.extend(_pairs_ending_in_money(_ordered_words(line)))
        results.append(_result_page(page.number, year, month, fields, bases))
    return results


def _five_columns_from_header(line: _Line) -> _FiveColumns | None:
    code = _word_with_semantic(line, "cod")
    label = _word_with_semantic(line, "descricao")
    reference = _word_with_semantic(line, "unidade")
    provents = _word_with_semantic(line, "proventos")
    discounts = _word_with_semantic(line, "descontos")
    if None in (code, label, reference, provents, discounts):
        return None
    assert code and label and reference and provents and discounts
    return _FiveColumns(
        label.bbox.x0,
        reference.bbox.x0,
        provents.bbox.x0,
        discounts.bbox.x0,
    )


def _sap_field(line: _Line, columns: _FiveColumns) -> dict[str, str] | None:
    words = _ordered_words(line)
    code_words = [word for word in words if word.bbox.center_x < columns.code_label]
    code = code_words[0].text.strip() if code_words else ""
    if not code or not _CODE_RE.fullmatch(code):
        return None
    label = " ".join(
        word.text
        for word in words
        if columns.code_label <= word.bbox.center_x < columns.label_reference
    ).strip()
    reference = " ".join(
        word.text
        for word in words
        if columns.label_reference <= word.bbox.center_x < columns.reference_provents
    ).strip()
    values = [
        value
        for word in words
        if word.bbox.center_x >= columns.reference_provents
        if (value := _money(word)) is not None
    ]
    if not label:
        return None
    return {
        "code": code,
        "label": label,
        "reference": reference,
        "value": values[0] if values else "",
    }


def _parse_sap(page: PdfPage, lines: list[_Line]) -> list[dict[str, Any]]:
    competence = next(
        (
            parsed
            for line in lines
            if "periodo" in _line_semantic(line)
            and (parsed := _numeric_competence(line)) is not None
        ),
        None,
    )
    header_index: int | None = None
    columns: _FiveColumns | None = None
    for index, line in enumerate(lines):
        candidate = _five_columns_from_header(line)
        if candidate is not None:
            header_index = index
            columns = candidate
            break
    if competence is None or header_index is None or columns is None:
        return []

    fields: list[dict[str, str]] = []
    total_index: int | None = None
    for index in range(header_index + 1, len(lines)):
        if _line_semantic(lines[index]).startswith("total"):
            total_index = index
            break
        field = _sap_field(lines[index], columns)
        if field:
            fields.append(field)

    bases: list[dict[str, str]] = []
    if total_index is not None:
        total_line = lines[total_index]
        provent_values = [
            value
            for word in _ordered_words(total_line)
            if columns.reference_provents <= word.bbox.center_x < columns.provents_discounts
            if (value := _money(word)) is not None
        ]
        discount_values = [
            value
            for word in _ordered_words(total_line)
            if word.bbox.center_x >= columns.provents_discounts
            if (value := _money(word)) is not None
        ]
        if provent_values:
            bases.append({"label": "Total Proventos", "value": provent_values[0]})
        if discount_values:
            bases.append({"label": "Total Descontos", "value": discount_values[0]})
        for line in lines[total_index + 1 :]:
            if "assinadoeletronicamente" in _line_semantic(line):
                break
            bases.extend(_pairs_ending_in_money(_ordered_words(line)))

    year, month = competence
    return [_result_page(page.number, year, month, fields, bases)]


def _receipt_side_columns(header_words: list[PdfWord]) -> _ReceiptColumns | None:
    description = next(
        (word for word in header_words if _semantic_text(word.text) == "descricao"),
        None,
    )
    quantity = next(
        (word for word in header_words if _semantic_text(word.text) == "qtde"),
        None,
    )
    value = next(
        (word for word in header_words if _semantic_text(word.text) == "valor"),
        None,
    )
    if description is None or quantity is None or value is None:
        return None
    # Description ends at the quantity column's left edge. Monetary values are
    # right-aligned, so their glyphs can begin left of the centered "Valor"
    # header; the midpoint between quantity and value headings is the safe band
    # separator.
    average_header_character_width = (
        (description.bbox.x1 - description.bbox.x0) / max(len(description.text), 1)
    )
    return _ReceiptColumns(
        label_start=description.bbox.x0,
        label_reference=quantity.bbox.x0,
        reference_value=_boundary(quantity, value),
        # Receipt labels are flush with the description header / table edge.
        # A shift wider than almost one header glyph is evidence that
        # Tesseract lost the first glyph beside the vertical grid line. The
        # missing character itself remains unknown and is represented by '?'.
        missing_prefix_tolerance=max(1.0, average_header_character_width * 0.9),
    )


def _receipt_prefix_is_missing(
    first_word: PdfWord, columns: _ReceiptColumns
) -> bool:
    return (
        first_word.source == "ocr"
        and first_word.bbox.x0 - columns.label_start
        > columns.missing_prefix_tolerance
    )


def _mark_receipt_prefix(
    label: str, label_words: list[PdfWord], columns: _ReceiptColumns
) -> str:
    if label_words and _receipt_prefix_is_missing(label_words[0], columns):
        return f"?{label}"
    return label


def _receipt_field(
    words: list[PdfWord], columns: _ReceiptColumns
) -> dict[str, str] | None:
    value_candidates = [
        (word, value)
        for word in words
        if word.bbox.center_x >= columns.reference_value
        if (value := _money(word)) is not None
    ]
    if not value_candidates:
        return None
    value_word, value = value_candidates[-1]
    label_words = [
        word for word in words if word.bbox.center_x < columns.label_reference
    ]
    label = " ".join(word.text for word in label_words).strip()
    reference = " ".join(
        word.text
        for word in words
        if columns.label_reference <= word.bbox.center_x < columns.reference_value
        and word is not value_word
    ).strip()
    if not label:
        return None
    label = _mark_receipt_prefix(label, label_words, columns)
    return {"code": "", "label": label, "reference": reference, "value": value}


def _receipt_pairs_ending_in_money(
    words: list[PdfWord], columns: _ReceiptColumns
) -> list[dict[str, str]]:
    ordered = sorted(words, key=lambda word: word.bbox.x0)
    pairs = _pairs_ending_in_money(ordered)
    if not pairs:
        return pairs
    first_money = next((index for index, word in enumerate(ordered) if _money(word)), len(ordered))
    label_words = ordered[:first_money]
    pairs[0]["label"] = _mark_receipt_prefix(
        pairs[0]["label"], label_words, columns
    )
    return pairs


def _labels_above_values(
    label_words: list[PdfWord],
    value_words: list[PdfWord],
    first_columns: _ReceiptColumns | None = None,
) -> list[dict[str, str]]:
    values = [(word, value) for word in value_words if (value := _money(word)) is not None]
    if not values:
        return []
    centers = [word.bbox.center_x for word, _ in values]
    boundaries = [
        (left + right) / 2 for left, right in zip(centers, centers[1:])
    ]
    pairs: list[dict[str, str]] = []
    for index, (_, value) in enumerate(values):
        left = float("-inf") if index == 0 else boundaries[index - 1]
        right = float("inf") if index == len(values) - 1 else boundaries[index]
        words = [word for word in label_words if left <= word.bbox.center_x < right]
        label = _clean_base_label(words)
        if label:
            if index == 0 and first_columns is not None:
                label = _mark_receipt_prefix(label, words, first_columns)
            pairs.append({"label": label, "value": value})
    return pairs


def _parse_receipt_block(
    page: PdfPage, lines: list[_Line], start: int, end: int
) -> dict[str, Any] | None:
    section_header_index: int | None = None
    split_x: float | None = None
    for index in range(start + 1, end):
        line = lines[index]
        provents = _word_with_semantic(line, "proventos")
        discounts = _word_with_semantic(line, "descontos")
        if provents and discounts:
            section_header_index = index
            split_x = _boundary(provents, discounts)
            break
    if section_header_index is None or split_x is None:
        return None

    competence = next(
        (
            parsed
            for line in lines[start + 1 : section_header_index]
            if (parsed := _named_competence(line)) is not None
        ),
        ("", ""),
    )

    table_header_index: int | None = None
    left_columns: _ReceiptColumns | None = None
    right_columns: _ReceiptColumns | None = None
    table_right = page.width
    for index in range(section_header_index + 1, end):
        left_header = _zone_words(lines[index], 0, split_x)
        right_header = _zone_words(lines[index], split_x, page.width)
        left_candidate = _receipt_side_columns(left_header)
        right_candidate = _receipt_side_columns(right_header)
        if left_candidate and right_candidate:
            table_header_index = index
            left_columns = left_candidate
            right_columns = right_candidate
            table_right = max(word.bbox.x1 for word in right_header)
            break
    if table_header_index is None or left_columns is None or right_columns is None:
        return None

    fields: list[dict[str, str]] = []
    total_index: int | None = None
    for index in range(table_header_index + 1, end):
        line = lines[index]
        semantic = _line_semantic(line)
        if "proventos" in semantic and "descontos" in semantic:
            total_index = index
            break
        left = _zone_words(line, 0, split_x)
        right = _zone_words(line, split_x, table_right)
        left_field = _receipt_field(left, left_columns)
        right_field = _receipt_field(right, right_columns)
        if left_field:
            fields.append(left_field)
        if right_field:
            fields.append(right_field)

    bases: list[dict[str, str]] = []
    if total_index is not None:
        total_line = lines[total_index]
        bases.extend(
            _receipt_pairs_ending_in_money(
                _zone_words(total_line, 0, split_x), left_columns
            )
        )
        bases.extend(
            _receipt_pairs_ending_in_money(
                _zone_words(total_line, split_x, table_right), right_columns
            )
        )

        after_total = lines[total_index + 1 : end]
        liquid_position: int | None = None
        for position, line in enumerate(after_total):
            semantic = _line_semantic(line)
            if "liquido" in semantic and "receber" in semantic:
                pairs = _receipt_pairs_ending_in_money(
                    [
                        word
                        for word in _ordered_words(line)
                        if word.bbox.center_x < table_right
                    ],
                    right_columns,
                )
                if pairs:
                    bases.append(pairs[0])
                liquid_position = position
                break

        if liquid_position is not None:
            lower_lines = after_total[liquid_position + 1 :]
            for position, label_line in enumerate(lower_lines[:-1]):
                if any(_money(word) for word in label_line.words):
                    continue
                value_line = lower_lines[position + 1]
                values = [
                    word
                    for word in _ordered_words(value_line)
                    if word.bbox.center_x < table_right and _money(word)
                ]
                if len(values) < 2:
                    continue
                labels = [
                    word
                    for word in _ordered_words(label_line)
                    if word.bbox.center_x < table_right
                ]
                bases.extend(
                    _labels_above_values(labels, values, first_columns=left_columns)
                )
                break

    year, month = competence
    return _result_page(page.number, year, month, fields, bases)


def _parse_receipt(page: PdfPage, lines: list[_Line]) -> list[dict[str, Any]]:
    anchors = [
        index for index, line in enumerate(lines) if "recibodepagamento" in _line_semantic(line)
    ]
    parsed: list[dict[str, Any]] = []
    fingerprints: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for position, start in enumerate(anchors):
        end = anchors[position + 1] if position + 1 < len(anchors) else len(lines)
        result = _parse_receipt_block(page, lines, start, end)
        if result is None:
            continue
        fingerprint = (
            tuple(field["value"] for field in result["fields"]),
            tuple(base["value"] for base in result["bases"]),
        )
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        parsed.append(result)
    return parsed


def _extract_page(
    page: PdfPage,
    ledger_bounds: tuple[float, float] | None = None,
) -> list[dict[str, Any]]:
    lines = _make_lines(page)
    semantic_lines = [_line_semantic(line) for line in lines]
    if ledger_bounds is not None or any(
        all(token in semantic for token in ("rendimentos", "descontos", "resultados"))
        for semantic in semantic_lines
    ):
        results = _parse_ledger(page, lines, ledger_bounds)
    elif any("mesano" in semantic for semantic in semantic_lines):
        results = _parse_corporate(page, lines)
    elif any(
        all(token in semantic for token in ("descricao", "unidade", "proventos", "descontos"))
        for semantic in semantic_lines
    ):
        results = _parse_sap(page, lines)
    elif any("recibodepagamento" in semantic for semantic in semantic_lines):
        results = _parse_receipt(page, lines)
    else:
        results = []
    return results or [_empty_page(page.number)]


def extract_holerite_pages(pages: tuple[PdfPage, ...]) -> dict[str, Any]:
    """Extract already-read pages, preserving physical and block order."""

    ledger_ratios: tuple[float, float] | None = None
    for page in pages:
        if (bounds := _three_section_bounds(_make_lines(page))) is not None:
            ledger_ratios = (bounds[0] / page.width, bounds[1] / page.width)
            break

    extracted: list[dict[str, Any]] = []
    for page in pages:
        bounds = (
            (ledger_ratios[0] * page.width, ledger_ratios[1] * page.width)
            if ledger_ratios is not None
            else None
        )
        page_results = _extract_page(page, bounds)
        if ledger_ratios is not None and page_results:
            fragment = page_results[0]
            if (
                extracted
                and fragment["year"] == fragment["month"] == ""
                and (fragment["fields"] or fragment["bases"])
            ):
                previous = extracted[-1]
                previous_base_labels = {
                    _semantic_text(base["label"]) for base in previous["bases"]
                }
                block_is_open = not (
                    any(label.startswith(("totrendimentos", "totalrendimentos")) for label in previous_base_labels)
                    and any(label.startswith("totaldescontos") for label in previous_base_labels)
                )
                if block_is_open:
                    # The previous block has no structural closing totals and
                    # the new physical page begins with table-compatible rows.
                    # Appending the fragment completes that same printed block;
                    # it does not copy or infer a competence for a new record.
                    previous["fields"].extend(fragment["fields"])
                    previous["bases"].extend(fragment["bases"])
                    page_results = page_results[1:]
        extracted.extend(page_results or [_empty_page(page.number)])
    return {"pages": extracted}


def extract_holerite(pdf_path: str | PathLike[str]) -> dict[str, Any]:
    """Standalone entry point for payroll extraction."""

    return extract_holerite_pages(read_pdf(pdf_path))


__all__ = ["extract_holerite", "extract_holerite_pages"]
