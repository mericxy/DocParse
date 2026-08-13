"""Environment-backed application settings with development defaults."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


_DEFAULT_DATABASE_URL = "sqlite:///./data/transcricoes.db"
_DEFAULT_UPLOAD_DIR = Path("./data/uploads")


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    value = default if raw is None else int(raw)
    if value <= 0:
        raise ValueError(f"{name} deve ser maior que zero")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    value = default if raw is None else float(raw)
    if value <= 0:
        raise ValueError(f"{name} deve ser maior que zero")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = _DEFAULT_DATABASE_URL
    upload_dir: Path = _DEFAULT_UPLOAD_DIR
    max_upload_size_mb: int = 10
    job_stale_after_minutes: int = 30
    worker_poll_interval_seconds: float = 1.0
    retention_hours: int = 24
    cleanup_interval_seconds: float = 300.0
    sqlite_busy_timeout_ms: int = 5_000
    upload_chunk_size_bytes: int = 64 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL),
            upload_dir=Path(os.getenv("UPLOAD_DIR", str(_DEFAULT_UPLOAD_DIR))),
            max_upload_size_mb=_positive_int("MAX_UPLOAD_SIZE_MB", 10),
            job_stale_after_minutes=_positive_int("JOB_STALE_AFTER_MINUTES", 30),
            worker_poll_interval_seconds=_positive_float(
                "WORKER_POLL_INTERVAL_SECONDS", 1.0
            ),
            retention_hours=_positive_int("RETENTION_HOURS", 24),
            cleanup_interval_seconds=_positive_float(
                "CLEANUP_INTERVAL_SECONDS", 300.0
            ),
            sqlite_busy_timeout_ms=_positive_int("SQLITE_BUSY_TIMEOUT_MS", 5_000),
            upload_chunk_size_bytes=_positive_int(
                "UPLOAD_CHUNK_SIZE_BYTES", 64 * 1024
            ),
        )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024
