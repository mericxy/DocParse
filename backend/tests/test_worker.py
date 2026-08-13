from __future__ import annotations

from datetime import datetime, timedelta, UTC
from pathlib import Path

import pytest
from sqlalchemy import text

from backend.app.config import Settings
from backend.app.db.database import create_database, init_database
from backend.app.db.models import Transcription
from backend.worker import claim_next_job, cleanup_expired_jobs, process_next_job


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture
def worker_context(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'worker.db'}",
        upload_dir=tmp_path / "uploads",
        job_stale_after_minutes=30,
        worker_poll_interval_seconds=0.01,
        retention_hours=24,
        cleanup_interval_seconds=60,
    )
    engine, session_factory = create_database(settings)
    init_database(engine)
    yield settings, session_factory
    engine.dispose()


def _add_job(
    session_factory,
    *,
    job_id: str,
    tipo: str = "cartao-ponto",
    status: str = "processando",
    started_at: datetime | None = None,
    created_at: datetime | None = None,
    file_path: str = "/tmp/server-generated.pdf",
):
    with session_factory() as session:
        session.add(
            Transcription(
                id=job_id,
                tipo=tipo,
                status=status,
                erro=None,
                value=None,
                file_path=file_path,
                created_at=created_at or _now(),
                started_at=started_at,
                finished_at=None,
            )
        )
        session.commit()


def _cartao_result() -> dict:
    return {"pages": [{"page": 1, "days": []}]}


def _holerite_result() -> dict:
    return {
        "pages": [
            {"page": 1, "year": "2025", "month": "01", "fields": [], "bases": []}
        ]
    }


def test_process_next_job_returns_false_when_queue_is_empty(worker_context):
    settings, session_factory = worker_context
    assert process_next_job(session_factory, settings, extractors={}) is False


def test_sqlite_uses_wal_and_configured_busy_timeout(worker_context):
    settings, session_factory = worker_context
    engine = session_factory.kw["bind"]
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
        assert (
            connection.execute(text("PRAGMA busy_timeout")).scalar_one()
            == settings.sqlite_busy_timeout_ms
        )


@pytest.mark.parametrize(
    ("tipo", "result"),
    (("cartao-ponto", _cartao_result()), ("holerite", _holerite_result())),
)
def test_worker_dispatches_and_persists_valid_result(worker_context, tipo, result):
    settings, session_factory = worker_context
    _add_job(session_factory, job_id=tipo, tipo=tipo)
    calls: list[str] = []

    def extractor(path: str) -> dict:
        calls.append(path)
        return result

    assert process_next_job(session_factory, settings, extractors={tipo: extractor}) is True
    with session_factory() as session:
        job = session.get(Transcription, tipo)
        assert job.status == "concluido"
        assert job.value == result
        assert job.erro is None
        assert job.started_at is not None
        assert job.finished_at is not None
    assert calls == ["/tmp/server-generated.pdf"]


def test_extractor_failure_marks_job_and_does_not_escape_worker(worker_context):
    settings, session_factory = worker_context
    _add_job(session_factory, job_id="failed")

    def failing_extractor(_path: str) -> dict:
        raise RuntimeError("conteúdo sensível que não deve ser persistido")

    assert process_next_job(
        session_factory,
        settings,
        extractors={"cartao-ponto": failing_extractor},
    ) is True
    with session_factory() as session:
        job = session.get(Transcription, "failed")
        assert job.status == "erro"
        assert job.value is None
        assert job.erro == "Não foi possível processar o documento."
        assert "sensível" not in job.erro


def test_completed_job_is_not_claimed(worker_context):
    settings, session_factory = worker_context
    _add_job(session_factory, job_id="done", status="concluido")
    assert claim_next_job(session_factory, settings) is None


def test_atomic_claim_prevents_second_worker_from_getting_same_job(worker_context):
    settings, session_factory = worker_context
    _add_job(session_factory, job_id="single")
    claim_time = _now()

    first = claim_next_job(session_factory, settings, now=claim_time)
    second = claim_next_job(session_factory, settings, now=claim_time)

    assert first is not None
    assert first.id == "single"
    assert second is None


def test_stale_job_is_claimed_again_and_timestamp_is_refreshed(worker_context):
    settings, session_factory = worker_context
    current = _now()
    old_started_at = current - timedelta(minutes=31)
    _add_job(session_factory, job_id="stale", started_at=old_started_at)

    claimed = claim_next_job(session_factory, settings, now=current)

    assert claimed is not None
    assert claimed.id == "stale"
    assert claimed.started_at == current


def test_cleanup_removes_expired_record_and_file_but_tolerates_missing_file(
    worker_context, tmp_path: Path
):
    settings, session_factory = worker_context
    old = _now() - timedelta(hours=25)
    stored = tmp_path / "expired.pdf"
    stored.write_bytes(b"%PDF-test")
    _add_job(
        session_factory,
        job_id="with-file",
        created_at=old,
        file_path=str(stored),
    )
    _add_job(
        session_factory,
        job_id="missing-file",
        created_at=old,
        file_path=str(tmp_path / "already-gone.pdf"),
    )

    assert cleanup_expired_jobs(session_factory, settings, now=_now()) == 2
    assert not stored.exists()
    with session_factory() as session:
        assert session.get(Transcription, "with-file") is None
        assert session.get(Transcription, "missing-file") is None
