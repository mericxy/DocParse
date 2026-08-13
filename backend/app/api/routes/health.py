"""Minimal application and database health check."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text


router = APIRouter()


@router.get("/healthz")
def healthz(request: Request) -> dict[str, str]:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.") from exc
    return {"status": "ok"}
