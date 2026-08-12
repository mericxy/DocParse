"""Layout-aware extraction of time-card day rows and punches."""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
import re
from statistics import median
import unicodedata
from typing import Any

from ..pdf.models import BoundingBox, PdfPage, PdfWord
from ..pdf.reader import read_pdf


_FULL_DATE_RE = re.compile(
    r"(?<![0-9?])([0-9?]{1,2}([/.-])[0-9?]{1,2}\2[0-9?]{2,4})(?![0-9?])"
)
_SHORT_DAY_RE = re.compile(r"^[0-9?]{1,2}(?:[-.]?)$")
_TIME_RE = re.compile(
    r"(?<![0-9?A-Za-z])([+]?[0-9?]{1,2}\s*[:hH.]\s*[0-9?]{2}[A-Za-z]?)(?![0-9?A-Za-z])"
)

# PyMuPDF normally provides reliable line IDs for embedded text, but Tesseract
# can assign a different ID to every word on the same visual baseline. The
# tolerance is derived from the page's median word height instead of PDF sample
# coordinates. Less than half a word height keeps adjacent table rows apart.
_LINE_CENTER_TOLERANCE_HEIGHT_FACTOR = 0.45
_LINE_CENTER_TOLERANCE_PAGE_FACTOR = 0.001

# A continuation must be the next visual table line and have a vertical gap
# compatible with the page's own row rhythm. This prevents a later section with
# a clock-looking value from being attached to the last day.
_CONTINUATION_MAX_LINE_STEP_FACTOR = 1.6

# Headerless extraction can only exclude a right-side auxiliary column when a
# clear geometric separation exists. The value compares gaps inferred from the
# page itself; it is not an X coordinate from any fixture.
_FALLBACK_AUXILIARY_GAP_FACTOR = 2.0
_FALLBACK_X_CLUSTER_PAGE_FACTOR = 0.01

_DATE_HEADERS = {"data", "dia", "date"}
_PUNCH_HEADERS = {
    "entrada",
    "saida",
    "intervalo",
    "manha",
    "tarde",
    "extra",
}
_STOP_HEADERS = {
    "he",
    "hext",
    "atraso",
    "falta",
    "adnot",
    "abono",
    "noturno",
    "atn",
    "func",
    "situag",
    "situacao",
    "insalub",
    "conc",
    "ocorrencia",
    "qtde",
}
_TABLE_END_MARKERS = {
    "assinado",
    "codigo",
    "impresso",
    "resumo",
    "total",
    "totais",
}


@dataclass(slots=True)
class _Line:
    words: list[PdfWord]
    bbox: BoundingBox


@dataclass(frozen=True, slots=True)
class _Columns:
    header_last_line: int
    date_right: float
    punch_left: float
    punch_right: float
    detected_from_header: bool


def _semantic_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]", "", without_accents.casefold())


def _is_date_header(word: PdfWord) -> bool:
    return _semantic_text(word.text) in _DATE_HEADERS


def _is_punch_header(word: PdfWord) -> bool:
    token = _semantic_text(word.text)
    if token in _PUNCH_HEADERS:
        return True
    # Common compact headers: Ent1/Sai1. OCR often reads the digit 1 as I or L.
    return bool(re.fullmatch(r"(?:ent|sai)[0-9il]*", token))


def _is_stop_header(word: PdfWord) -> bool:
    return _semantic_text(word.text) in _STOP_HEADERS


def _make_lines(page: PdfPage) -> list[_Line]:
    """Group words on visual baselines while preserving their read sequence."""

    if not page.words:
        return []

    median_word_height = median(word.bbox.y1 - word.bbox.y0 for word in page.words)
    center_tolerance = max(
        median_word_height * _LINE_CENTER_TOLERANCE_HEIGHT_FACTOR,
        page.height * _LINE_CENTER_TOLERANCE_PAGE_FACTOR,
    )
    lines: list[_Line] = []
    for word in page.words:
        closest_line: _Line | None = None
        closest_distance = float("inf")
        for candidate in lines:
            distance = abs(candidate.bbox.center_y - word.bbox.center_y)
            if distance <= center_tolerance and distance < closest_distance:
                closest_line = candidate
                closest_distance = distance

        if closest_line is None:
            lines.append(_Line(words=[word], bbox=word.bbox))
            continue

        closest_line.words.append(word)
        closest_line.bbox = BoundingBox(
            min(closest_line.bbox.x0, word.bbox.x0),
            min(closest_line.bbox.y0, word.bbox.y0),
            max(closest_line.bbox.x1, word.bbox.x1),
            max(closest_line.bbox.y1, word.bbox.y1),
        )
    return lines


def _locate_columns_from_header(lines: list[_Line], page_width: float) -> _Columns | None:
    """Find table columns semantically from a header spanning up to 3 lines."""

    for start in range(len(lines)):
        window_words: list[PdfWord] = []
        semantic_line_indexes: list[int] = []
        last = min(start + 3, len(lines))
        for line_index in range(start, last):
            window_words.extend(lines[line_index].words)
            if any(
                _is_date_header(word) or _is_punch_header(word) or _is_stop_header(word)
                for word in lines[line_index].words
            ):
                semantic_line_indexes.append(line_index)

        date_words = [word for word in window_words if _is_date_header(word)]
        punch_words = [word for word in window_words if _is_punch_header(word)]
        if not date_words or not punch_words:
            continue

        date_right = max(word.bbox.x1 for word in date_words)
        punch_left = min(word.bbox.x0 for word in punch_words)
        last_punch_x = max(word.bbox.x1 for word in punch_words)

        stop_left: float | None = None
        for word in window_words:
            if _is_stop_header(word) and word.bbox.x0 > last_punch_x:
                if stop_left is None or word.bbox.x0 < stop_left:
                    stop_left = word.bbox.x0

        punch_right = page_width if stop_left is None else stop_left
        return _Columns(
            header_last_line=max(semantic_line_indexes),
            date_right=max(date_right, punch_left),
            punch_left=punch_left,
            punch_right=punch_right,
            detected_from_header=True,
        )
    return None


def _date_match(word: PdfWord, *, allow_short_day: bool) -> str | None:
    full = _FULL_DATE_RE.search(word.text)
    if full:
        return full.group(1)
    stripped = word.text.strip()
    if allow_short_day and _SHORT_DAY_RE.fullmatch(stripped):
        return stripped.rstrip("-.")
    return None


def _fallback_columns(lines: list[_Line], page_width: float) -> _Columns | None:
    """Isolated fallback: infer bands from date/time tokens on the page.

    Without semantic headers an auxiliary time cannot always be distinguished
    from an additional punch. We only cut the band when the right-side token is
    separated by a gap clearly larger than the other detected column gaps.
    """

    date_words: list[PdfWord] = []
    time_words: list[PdfWord] = []
    first_date_line: int | None = None
    for line_index, line in enumerate(lines):
        for word in line.words:
            if _date_match(word, allow_short_day=False):
                date_words.append(word)
                if first_date_line is None:
                    first_date_line = line_index
            if _TIME_RE.search(word.text):
                time_words.append(word)

    if not date_words or not time_words or first_date_line is None:
        return None

    date_right = max(word.bbox.x1 for word in date_words)
    punches_after_dates = [word for word in time_words if word.bbox.x0 >= date_right]
    if not punches_after_dates:
        return None

    x_tolerance = page_width * _FALLBACK_X_CLUSTER_PAGE_FACTOR
    x_clusters: list[list[float]] = []
    for center_x in sorted(word.bbox.center_x for word in punches_after_dates):
        if not x_clusters or center_x - median(x_clusters[-1]) > x_tolerance:
            x_clusters.append([center_x])
        else:
            x_clusters[-1].append(center_x)

    cluster_centers = [median(cluster) for cluster in x_clusters]
    punch_right: float | None = None
    if len(cluster_centers) >= 3:
        gaps = [right - left for left, right in zip(cluster_centers, cluster_centers[1:])]
        largest_gap = max(gaps)
        largest_index = gaps.index(largest_gap)
        other_gaps = [gap for index, gap in enumerate(gaps) if index != largest_index]
        if other_gaps and largest_gap >= median(other_gaps) * _FALLBACK_AUXILIARY_GAP_FACTOR:
            punch_right = (
                cluster_centers[largest_index] + cluster_centers[largest_index + 1]
            ) / 2

    if punch_right is None:
        punch_right = min(
            page_width,
            max(word.bbox.x1 for word in punches_after_dates) + page_width * 0.02,
        )

    return _Columns(
        header_last_line=first_date_line - 1,
        date_right=date_right,
        punch_left=min(word.bbox.x0 for word in punches_after_dates),
        punch_right=punch_right,
        detected_from_header=False,
    )


def _component_has_valid_value(component: str, maximum: int) -> bool:
    possibilities = [""]
    for character in component:
        digits = "0123456789" if character == "?" else character
        possibilities = [prefix + digit for prefix in possibilities for digit in digits]
    return any(int(value) <= maximum for value in possibilities)


def normalize_time_hhmm(time_raw: str) -> str:
    """Normalize only safe formatting and mark impossible components unknown."""

    compact = re.sub(r"\s+", "", time_raw)
    match = re.fullmatch(
        r"[+]?([0-9?]{1,2})[:hH.]([0-9?]{2})([A-Za-z]?)",
        compact,
    )
    if not match:
        return time_raw

    hour, minute, suffix = match.groups()
    if suffix and suffix.casefold() not in {"c", "d"}:
        # Only c/d are evidenced status markers in the audited layouts. An
        # unknown suffix remains visible instead of being silently discarded.
        return time_raw
    # Uncertain digits are preserved character-for-character. Decorations such
    # as a rollover '+' or a trailing status marker belong only to ``time_raw``.
    if "?" in hour or "?" in minute:
        return f"{hour}:{minute}"
    if "?" not in hour and len(hour) == 1:
        hour = f"0{hour}"

    if not _component_has_valid_value(hour, 23):
        hour = "?" * len(hour)
    if not _component_has_valid_value(minute, 59):
        minute = "??"
    return f"{hour}:{minute}"


def _times_in_line(line: _Line, columns: _Columns) -> list[str]:
    times: list[str] = []
    for word in line.words:
        if not columns.punch_left <= word.bbox.center_x < columns.punch_right:
            continue
        for match in _TIME_RE.finditer(word.text):
            times.append(match.group(1))
    return times


def _line_starts_footer(line: _Line) -> bool:
    tokens = {_semantic_text(word.text) for word in line.words}
    return bool(tokens & _TABLE_END_MARKERS)


def _typical_line_step(lines: list[_Line], start_index: int) -> float:
    centers = [line.bbox.center_y for line in lines[start_index:]]
    positive_steps = [right - left for left, right in zip(centers, centers[1:]) if right > left]
    return median(positive_steps) if positive_steps else 0.0


def _is_adjacent_continuation(
    *,
    line: _Line,
    line_index: int,
    previous_line: _Line | None,
    previous_line_index: int | None,
    typical_line_step: float,
    columns: _Columns,
    date_raw: str | None,
    current_day: dict[str, Any] | None,
    line_times: list[str],
) -> bool:
    """Accept only a geometrically adjacent, table-compatible continuation."""

    if (
        current_day is None
        or previous_line is None
        or previous_line_index is None
        or line_index != previous_line_index + 1
        or _line_starts_footer(line)
    ):
        return False

    vertical_gap = line.bbox.center_y - previous_line.bbox.center_y
    if vertical_gap <= 0:
        return False
    if typical_line_step and vertical_gap > typical_line_step * _CONTINUATION_MAX_LINE_STEP_FACTOR:
        return False

    if date_raw is not None:
        # A repeated label is continuation evidence only when the previous
        # record already had punches. Adjacency and row geometry are also
        # required, so equality alone never merges records.
        return date_raw == current_day["date_raw"] and bool(current_day["punches"])

    # A date-less continuation must not contain a label or other alphanumeric
    # content to the left of the punch region.
    if not line_times:
        return False
    incompatible_prefix = any(
        word.bbox.x0 < columns.punch_left and _semantic_text(word.text)
        for word in line.words
    )
    return not incompatible_prefix


def _extract_page(page: PdfPage) -> dict[str, Any]:
    lines = _make_lines(page)
    columns = _locate_columns_from_header(lines, page.width)
    if columns is None:
        columns = _fallback_columns(lines, page.width)
    if columns is None:
        return {"page": page.number, "days": []}

    days: list[dict[str, Any]] = []
    current_day: dict[str, Any] | None = None
    previous_record_line: _Line | None = None
    previous_record_line_index: int | None = None
    typical_line_step = _typical_line_step(lines, columns.header_last_line + 1)
    for line_index in range(columns.header_last_line + 1, len(lines)):
        line = lines[line_index]
        if current_day is not None and _line_starts_footer(line):
            break

        date_raw: str | None = None
        for word in line.words:
            if word.bbox.x0 >= columns.punch_left:
                continue
            candidate = _date_match(word, allow_short_day=columns.detected_from_header)
            if candidate is not None:
                # date_raw is a literal transcription field. Plausibility is a
                # separate, derived concern and must never rewrite this value.
                date_raw = candidate
                break

        line_times = _times_in_line(line, columns)
        is_continuation = _is_adjacent_continuation(
            line=line,
            line_index=line_index,
            previous_line=previous_record_line,
            previous_line_index=previous_record_line_index,
            typical_line_step=typical_line_step,
            columns=columns,
            date_raw=date_raw,
            current_day=current_day,
            line_times=line_times,
        )
        if date_raw is not None:
            if not is_continuation:
                punches: list[dict[str, str]] = []
                current_day = {"date_raw": date_raw, "punches": punches}
                days.append(current_day)
        elif not is_continuation:
            previous_record_line = None
            previous_record_line_index = None
            continue

        if line_times and current_day is not None:
            punches = current_day["punches"]
            for time_raw in line_times:
                punches.append(
                    {
                        "kind": "IN" if len(punches) % 2 == 0 else "OUT",
                        "time_raw": time_raw,
                        "time_hhmm": normalize_time_hhmm(time_raw),
                    }
                )

        previous_record_line = line
        previous_record_line_index = line_index

    return {"page": page.number, "days": days}


def extract_cartao_ponto_pages(pages: tuple[PdfPage, ...]) -> dict[str, Any]:
    """Extract already-read pages; useful for tests and the future worker."""

    return {"pages": [_extract_page(page) for page in pages]}


def extract_cartao_ponto(pdf_path: str | PathLike[str]) -> dict[str, Any]:
    """Public standalone entry point required by the time-card pipeline."""

    return extract_cartao_ponto_pages(read_pdf(pdf_path))
