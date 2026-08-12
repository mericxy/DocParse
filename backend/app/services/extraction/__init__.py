"""Document-specific extractors built on the shared PDF representation."""

from .cartao_ponto import (
    extract_cartao_ponto,
    extract_cartao_ponto_pages,
    normalize_time_hhmm,
)
from .holerite import extract_holerite, extract_holerite_pages

__all__ = [
    "extract_cartao_ponto",
    "extract_cartao_ponto_pages",
    "extract_holerite",
    "extract_holerite_pages",
    "normalize_time_hhmm",
]
