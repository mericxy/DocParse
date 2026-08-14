"""Literal transcription upload, status, correction and download routes."""

from __future__ import annotations

from datetime import datetime, UTC
import logging
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.models import Transcription
from ...schemas import (
    TranscriptionCreated,
    TranscriptionResponse,
    ValueUpdate,
    validate_transcription_value,
)
from ...services.export import AmbiguousPayrollExportError, export_transcription
from ...services.uploads import InvalidPdfError, UploadTooLargeError, save_validated_pdf
from ..dependencies import get_session, get_settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transcricoes", tags=["transcricoes"])


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_or_404(session: Session, transcription_id: str) -> Transcription:
    transcription = session.get(Transcription, transcription_id)
    if transcription is None:
        raise HTTPException(status_code=404, detail="Transcrição não encontrada.")
    return transcription


def _public_response(transcription: Transcription) -> TranscriptionResponse:
    value = None
    if transcription.status == "concluido" and transcription.value is not None:
        value = validate_transcription_value(transcription.tipo, transcription.value)
    return TranscriptionResponse(
        id=transcription.id,
        tipo=transcription.tipo,
        status=transcription.status,
        erro=transcription.erro,
        value=value,
    )


@router.post("", status_code=202, response_model=TranscriptionCreated)
def create_transcription(
    arquivo: Annotated[UploadFile, File(...)],
    tipo: Annotated[Literal["cartao-ponto", "holerite"], Form(...)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TranscriptionCreated:
    transcription_id = str(uuid4())
    try:
        file_path, file_size = save_validated_pdf(
            arquivo, transcription_id, settings
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=f"O arquivo excede o limite de {settings.max_upload_size_mb} MB.",
        ) from exc
    except InvalidPdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    transcription = Transcription(
        id=transcription_id,
        tipo=tipo,
        status="processando",
        erro=None,
        value=None,
        file_path=str(file_path),
        created_at=_utcnow(),
        started_at=None,
        finished_at=None,
    )
    try:
        session.add(transcription)
        session.commit()
    except Exception:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise

    logger.info(
        "transcription_created id=%s tipo=%s status=processando file_size=%d",
        transcription_id,
        tipo,
        file_size,
    )
    return TranscriptionCreated(id=transcription_id)


@router.get("/{transcription_id}", response_model=TranscriptionResponse)
def get_transcription(
    transcription_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> TranscriptionResponse:
    return _public_response(_get_or_404(session, transcription_id))


@router.put("/{transcription_id}", response_model=TranscriptionResponse)
def update_transcription(
    transcription_id: str,
    body: ValueUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> TranscriptionResponse:
    transcription = _get_or_404(session, transcription_id)
    if transcription.status != "concluido":
        raise HTTPException(
            status_code=409,
            detail="Somente transcrições concluídas podem ser editadas.",
        )
    try:
        value = validate_transcription_value(transcription.tipo, body.value)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_input=False),
        ) from exc

    transcription.value = value
    transcription.erro = None
    session.commit()
    logger.info(
        "transcription_updated id=%s tipo=%s status=concluido",
        transcription.id,
        transcription.tipo,
    )
    return _public_response(transcription)


@router.get("/{transcription_id}/planilha")
def download_transcription(
    transcription_id: str,
    formato: Literal["xlsx", "csv", "json"],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    transcription = _get_or_404(session, transcription_id)
    if transcription.status == "processando":
        raise HTTPException(status_code=409, detail="A transcrição ainda está processando.")
    if transcription.status == "erro":
        raise HTTPException(
            status_code=409,
            detail=transcription.erro or "A transcrição terminou com erro.",
        )
    if transcription.value is None:
        raise HTTPException(status_code=409, detail="A transcrição não possui resultado.")

    value = validate_transcription_value(transcription.tipo, transcription.value)
    try:
        exported = export_transcription(transcription.tipo, formato, value)
    except AmbiguousPayrollExportError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    generated_name = f"transcricao-{transcription.id}.{exported.extension}"
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{generated_name}"'},
    )
