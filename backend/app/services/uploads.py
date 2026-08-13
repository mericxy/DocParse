"""Chunked upload persistence and defensive PDF validation."""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile
import pymupdf

from ..config import Settings


class UploadTooLargeError(ValueError):
    pass


class InvalidPdfError(ValueError):
    pass


def _unlink(path: Path) -> None:
    path.unlink(missing_ok=True)


def save_validated_pdf(
    upload: UploadFile,
    transcription_id: str,
    settings: Settings,
) -> tuple[Path, int]:
    """Stream an upload to a server-generated path and validate its contents."""

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.upload_dir / f"{transcription_id}.pdf"
    total_bytes = 0
    try:
        with destination.open("xb") as output:
            while chunk := upload.file.read(settings.upload_chunk_size_bytes):
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_size_bytes:
                    raise UploadTooLargeError
                output.write(chunk)
    except Exception:
        _unlink(destination)
        raise
    finally:
        upload.file.close()

    try:
        with destination.open("rb") as stored:
            if stored.read(5) != b"%PDF-":
                raise InvalidPdfError("O arquivo enviado não é um PDF válido.")
        try:
            document = pymupdf.open(destination)
        except Exception as exc:
            raise InvalidPdfError("O PDF enviado está corrompido ou é inválido.") from exc
        try:
            if not document.is_pdf:
                raise InvalidPdfError("O arquivo enviado não é um PDF válido.")
            if document.page_count < 1:
                raise InvalidPdfError("O PDF enviado não possui páginas.")
        finally:
            document.close()
    except Exception:
        _unlink(destination)
        raise

    return destination, total_bytes
