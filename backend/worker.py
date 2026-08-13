"""Separate polling worker for persisted extraction jobs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
import logging
from pathlib import Path
import time
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from .app.config import Settings
from .app.db.database import create_database, init_database
from .app.db.models import Transcription
from .app.schemas import validate_transcription_value
from .app.services.extraction import extract_cartao_ponto, extract_holerite


logger = logging.getLogger(__name__)
Extractor = Callable[[str], dict[str, Any]]
EXTRACTORS: Mapping[str, Extractor] = {
    "cartao-ponto": extract_cartao_ponto,
    "holerite": extract_holerite,
}


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: str
    tipo: str
    file_path: str
    started_at: datetime


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def claim_next_job(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    now: datetime | None = None,
) -> ClaimedJob | None:
    """Atomically claim one new or stale processing job in a short transaction."""

    claim_time = now or _utcnow()
    stale_before = claim_time - timedelta(minutes=settings.job_stale_after_minutes)
    eligible = or_(
        Transcription.started_at.is_(None),
        Transcription.started_at < stale_before,
    )
    candidate = (
        select(Transcription.id)
        .where(Transcription.status == "processando", eligible)
        .order_by(Transcription.created_at, Transcription.id)
        .limit(1)
        .scalar_subquery()
    )
    statement = (
        update(Transcription)
        .where(Transcription.id == candidate)
        .values(started_at=claim_time, finished_at=None, erro=None, value=None)
        .returning(
            Transcription.id,
            Transcription.tipo,
            Transcription.file_path,
            Transcription.started_at,
        )
    )
    with session_factory() as session:
        row = session.execute(statement).one_or_none()
        session.commit()
    if row is None:
        return None
    return ClaimedJob(row.id, row.tipo, row.file_path, row.started_at)


def _persist_success(
    session_factory: sessionmaker[Session],
    job: ClaimedJob,
    value: dict[str, Any],
    *,
    finished_at: datetime,
) -> bool:
    statement = (
        update(Transcription)
        .where(
            Transcription.id == job.id,
            Transcription.status == "processando",
            Transcription.started_at == job.started_at,
        )
        .values(status="concluido", value=value, erro=None, finished_at=finished_at)
    )
    with session_factory() as session:
        result = session.execute(statement)
        session.commit()
        return result.rowcount == 1


def _persist_error(
    session_factory: sessionmaker[Session],
    job: ClaimedJob,
    *,
    finished_at: datetime,
) -> bool:
    statement = (
        update(Transcription)
        .where(
            Transcription.id == job.id,
            Transcription.status == "processando",
            Transcription.started_at == job.started_at,
        )
        .values(
            status="erro",
            value=None,
            erro="Não foi possível processar o documento.",
            finished_at=finished_at,
        )
    )
    with session_factory() as session:
        result = session.execute(statement)
        session.commit()
        return result.rowcount == 1


def process_next_job(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    extractors: Mapping[str, Extractor] = EXTRACTORS,
    now: datetime | None = None,
) -> bool:
    """Claim and process at most one job; suitable for tests and the worker loop."""

    job = claim_next_job(session_factory, settings, now=now)
    if job is None:
        return False

    started_clock = time.monotonic()
    logger.info(
        "transcription_claimed id=%s tipo=%s status=processando",
        job.id,
        job.tipo,
    )
    try:
        extractor = extractors[job.tipo]
        extracted = extractor(job.file_path)
        value = validate_transcription_value(job.tipo, extracted)
        saved = _persist_success(
            session_factory,
            job,
            value,
            finished_at=_utcnow(),
        )
        logger.info(
            "transcription_finished id=%s tipo=%s status=%s duration_ms=%d",
            job.id,
            job.tipo,
            "concluido" if saved else "superseded",
            round((time.monotonic() - started_clock) * 1000),
        )
    except Exception as exc:
        saved = _persist_error(session_factory, job, finished_at=_utcnow())
        logger.error(
            "transcription_failed id=%s tipo=%s status=%s duration_ms=%d error_type=%s",
            job.id,
            job.tipo,
            "erro" if saved else "superseded",
            round((time.monotonic() - started_clock) * 1000),
            type(exc).__name__,
        )
    return True


def cleanup_expired_jobs(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    """Remove database rows and their server-generated PDFs after retention."""

    cutoff = (now or _utcnow()) - timedelta(hours=settings.retention_hours)
    with session_factory() as session:
        expired = session.execute(
            select(Transcription.id, Transcription.file_path).where(
                Transcription.created_at < cutoff
            )
        ).all()
        if not expired:
            return 0
        ids = [row.id for row in expired]
        session.execute(delete(Transcription).where(Transcription.id.in_(ids)))
        session.commit()

    for row in expired:
        Path(row.file_path).unlink(missing_ok=True)
    logger.info("transcription_cleanup status=concluido removed_count=%d", len(expired))
    return len(expired)


def run_worker(settings: Settings | None = None) -> None:
    resolved = settings or Settings.from_env()
    engine, session_factory = create_database(resolved)
    init_database(engine)
    next_cleanup = 0.0
    logger.info("worker_started status=ready")
    try:
        while True:
            current_clock = time.monotonic()
            if current_clock >= next_cleanup:
                cleanup_expired_jobs(session_factory, resolved)
                next_cleanup = current_clock + resolved.cleanup_interval_seconds
            processed = process_next_job(session_factory, resolved)
            if not processed:
                time.sleep(resolved.worker_poll_interval_seconds)
    finally:
        engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        run_worker()
    except KeyboardInterrupt:
        logger.info("worker_stopped status=interrupted")


if __name__ == "__main__":
    main()
