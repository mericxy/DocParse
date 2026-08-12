from __future__ import annotations

from collections.abc import Sequence

import pytest

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
