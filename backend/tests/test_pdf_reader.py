from __future__ import annotations

import pymupdf

from backend.app.services.pdf.models import BoundingBox, PdfWord
from backend.app.services.pdf import reader
from backend.app.services.pdf.reader import has_useful_text


def _word(text: str, sequence: int, *, y0: float = 0) -> PdfWord:
    return PdfWord(
        text=text,
        bbox=BoundingBox(0, y0, 10, y0 + 10),
        page=1,
        block=0,
        line=0,
        word=sequence,
        sequence=sequence,
        source="embedded",
    )


def test_useful_text_heuristic_rejects_scanner_noise():
    assert not has_useful_text((_word("x", 0), _word("|", 1), _word("1", 2)))
    assert has_useful_text(
        (
            _word("Data", 0, y0=0),
            _word("Entrada", 1, y0=20),
            _word("Saída", 2, y0=20),
            _word("01/05/2025", 3, y0=40),
        )
    )


def test_sparse_stamp_over_scan_is_not_a_useful_text_layer():
    stamp_words = tuple(
        _word(text, sequence, y0=0 if sequence < 2 else 780)
        for sequence, text in enumerate(
            ("Fls.", "316", "Assinado", "eletronicamente", "por", "Juntado", "em")
        )
    )

    assert not has_useful_text(stamp_words)


def test_reader_runs_ocr_only_for_page_without_useful_text(tmp_path, monkeypatch):
    pdf_path = tmp_path / "two-pages.pdf"
    document = pymupdf.open()
    document.new_page()
    document.new_page()
    document.save(pdf_path)
    document.close()

    ocr_pages: list[int] = []

    def fake_extract(page, *, page_number, source, textpage=None):
        if source == "embedded" and page_number == 2:
            return ()
        return tuple(
            _word(text, sequence, y0=sequence * 20)
            for sequence, text in enumerate(("Data", "Entrada", "Saída", "01/05/2025"))
        )

    def fake_ocr(page, *, language, dpi):
        ocr_pages.append(page.number + 1)
        return object()

    monkeypatch.setattr(reader, "_extract_words", fake_extract)
    monkeypatch.setattr(reader, "create_ocr_textpage", fake_ocr)

    pages = reader.read_pdf(pdf_path)

    assert [page.source for page in pages] == ["embedded", "ocr"]
    assert ocr_pages == [2]
