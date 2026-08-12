"""Read PDFs page by page, using OCR only when the text layer is not useful."""

from __future__ import annotations

from collections.abc import Iterable
from os import PathLike
from statistics import median

import pymupdf

from .models import BoundingBox, PdfPage, PdfWord
from .ocr import create_ocr_textpage


class PdfReadError(RuntimeError):
    """Raised when the input cannot be read as a PDF."""


def has_useful_text(words: Iterable[PdfWord]) -> bool:
    """Return whether extracted words look like an actual text layer.

    A non-empty layer is insufficient because scanners sometimes add a handful
    of control marks or broken glyphs. The page is considered useful when it
    has at least four tokens containing alphanumeric content and at least 20
    alphanumeric characters in total. Short layers (fewer than 20 informative
    tokens) must also span at least three visual lines. This last condition is
    generic: it rejects sparse stamps / page numbers laid over scanned pages,
    while still accepting compact, genuinely textual documents. Longer text
    layers do not need the visual-line check.
    """

    materialized_words = tuple(words)
    informative_words: list[PdfWord] = []
    alphanumeric_characters = 0
    for word in materialized_words:
        count = sum(character.isalnum() for character in word.text)
        if count:
            informative_words.append(word)
            alphanumeric_characters += count

    if len(informative_words) < 4 or alphanumeric_characters < 20:
        return False
    if len(informative_words) >= 20:
        return True

    median_height = median(word.bbox.y1 - word.bbox.y0 for word in informative_words)
    line_tolerance = max(1.0, median_height * 0.5)
    line_centers: list[float] = []
    for center_y in sorted(word.bbox.center_y for word in informative_words):
        if not line_centers or center_y - line_centers[-1] > line_tolerance:
            line_centers.append(center_y)
    return len(line_centers) >= 3


def _extract_words(
    page: pymupdf.Page,
    *,
    page_number: int,
    source: str,
    textpage: pymupdf.TextPage | None = None,
) -> tuple[PdfWord, ...]:
    # PyMuPDF's sort=True establishes visual top-to-bottom, left-to-right order.
    # We store that sequence as well as the original block/line/word indexes.
    raw_words = page.get_text("words", textpage=textpage, sort=True)
    result: list[PdfWord] = []
    for sequence, raw in enumerate(raw_words):
        x0, y0, x1, y1, text, block, line, word = raw[:8]
        result.append(
            PdfWord(
                text=str(text).replace("\ufffd", "?"),
                bbox=BoundingBox(float(x0), float(y0), float(x1), float(y1)),
                page=page_number,
                block=int(block),
                line=int(line),
                word=int(word),
                sequence=sequence,
                source=source,  # type: ignore[arg-type]
            )
        )
    return tuple(result)


def read_pdf(
    pdf_path: str | PathLike[str],
    *,
    ocr_language: str = "por+eng",
    ocr_dpi: int = 300,
) -> tuple[PdfPage, ...]:
    """Read every page without changing the PDF's page order."""

    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        raise PdfReadError(f"Não foi possível abrir o PDF: {pdf_path}") from exc

    pages: list[PdfPage] = []
    try:
        if not document.is_pdf:
            raise PdfReadError(f"O arquivo não é um PDF válido: {pdf_path}")

        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_number = page_index + 1
            embedded_words = _extract_words(
                page,
                page_number=page_number,
                source="embedded",
            )

            if has_useful_text(embedded_words):
                words = embedded_words
                source = "embedded"
            else:
                textpage = create_ocr_textpage(
                    page,
                    language=ocr_language,
                    dpi=ocr_dpi,
                )
                words = _extract_words(
                    page,
                    page_number=page_number,
                    source="ocr",
                    textpage=textpage,
                )
                source = "ocr"

            pages.append(
                PdfPage(
                    number=page_number,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    words=words,
                    source=source,  # type: ignore[arg-type]
                )
            )
    finally:
        document.close()

    return tuple(pages)
