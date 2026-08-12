"""Small, layout-preserving intermediate representation for PDF pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass(frozen=True, slots=True)
class PdfWord:
    text: str
    bbox: BoundingBox
    page: int
    block: int
    line: int
    word: int
    sequence: int
    source: Literal["embedded", "ocr"]
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class PdfPage:
    number: int
    width: float
    height: float
    words: tuple[PdfWord, ...]
    source: Literal["embedded", "ocr"]
