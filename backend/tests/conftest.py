from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.pdf.models import BoundingBox, PdfPage, PdfWord


@pytest.fixture
def make_page():
    def factory(
        lines: Sequence[Sequence[tuple[str, float]]],
        *,
        page_number: int = 1,
        width: float = 400,
    ) -> PdfPage:
        words: list[PdfWord] = []
        sequence = 0
        for line_index, line in enumerate(lines):
            y0 = 20.0 + line_index * 20.0
            for word_index, (text, x0) in enumerate(line):
                word_width = max(12.0, len(text) * 6.0)
                words.append(
                    PdfWord(
                        text=text,
                        bbox=BoundingBox(x0, y0, x0 + word_width, y0 + 10.0),
                        page=page_number,
                        block=0,
                        line=line_index,
                        word=word_index,
                        sequence=sequence,
                        source="embedded",
                    )
                )
                sequence += 1
        return PdfPage(
            number=page_number,
            width=width,
            height=800,
            words=tuple(words),
            source="embedded",
        )

    return factory


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Documento de teste")
    content = document.tobytes()
    document.close()
    return content


@pytest.fixture
def app_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=tmp_path / "uploads",
        max_upload_size_mb=1,
        job_stale_after_minutes=30,
        worker_poll_interval_seconds=0.01,
        retention_hours=24,
        cleanup_interval_seconds=60,
    )


@pytest.fixture
def client(app_settings: Settings):
    application = create_app(app_settings)
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def cartao_value() -> dict:
    return {
        "pages": [
            {
                "page": 1,
                "days": [
                    {
                        "date_raw": "01/01/2025",
                        "punches": [
                            {"kind": "IN", "time_raw": "8:00", "time_hhmm": "08:00"},
                            {"kind": "OUT", "time_raw": "12:00", "time_hhmm": "12:00"},
                        ],
                    }
                ],
            }
        ]
    }


@pytest.fixture
def holerite_value() -> dict:
    return {
        "pages": [
            {
                "page": 1,
                "year": "2025",
                "month": "01",
                "fields": [
                    {
                        "code": "0010",
                        "label": "Salário Base",
                        "reference": "220,00",
                        "value": "2.389,77",
                    }
                ],
                "bases": [{"label": "Base INSS", "value": "2.389,77"}],
            }
        ]
    }
