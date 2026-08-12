"""Minimal extractor contract for the future shared worker pipeline."""

from __future__ import annotations

from collections.abc import Callable
from os import PathLike
from typing import Any, Protocol

from ..pdf.models import PdfPage


PdfReader = Callable[[str | PathLike[str]], tuple[PdfPage, ...]]


class Extractor(Protocol):
    def __call__(self, pdf_path: str | PathLike[str]) -> dict[str, Any]: ...
