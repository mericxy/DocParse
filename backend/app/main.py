"""FastAPI application factory for the transcription backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import health_router, transcriptions_router
from .config import Settings
from .db.database import create_database, init_database


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    engine, session_factory = create_database(resolved_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        resolved_settings.upload_dir.mkdir(parents=True, exist_ok=True)
        init_database(engine)
        yield
        engine.dispose()

    application = FastAPI(title="DocParse", lifespan=lifespan)
    application.state.settings = resolved_settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.include_router(health_router)
    application.include_router(transcriptions_router)
    return application


app = create_app()
