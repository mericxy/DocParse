"""OCR adapter kept separate from normal PDF text extraction."""

from __future__ import annotations

import pymupdf


class OcrError(RuntimeError):
    """Raised when a page that needs OCR cannot be recognized."""


def create_ocr_textpage(
    page: pymupdf.Page,
    *,
    language: str = "por+eng",
    dpi: int = 300,
) -> pymupdf.TextPage:
    """Rasterize and OCR one page using Tesseract through PyMuPDF.

    This function is only called after the normal text layer failed the useful
    text heuristic. ``full=True`` is intentional: at that point the existing
    layer is absent or noise and must not be mixed with the OCR reading.
    """

    try:
        return page.get_textpage_ocr(
            language=language,
            dpi=dpi,
            full=True,
        )
    except Exception as exc:  # PyMuPDF exposes different OCR errors by version.
        raise OcrError(
            "Não foi possível executar OCR. Verifique o Tesseract e os "
            "idiomas 'por'/'eng' instalados."
        ) from exc
