"""App factory: build a fully wired FastAPI app from settings."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from patentpath.api.errors import (
    http_exception_handler,
    validation_exception_handler,
)
from patentpath.api.middleware import RequestLoggingMiddleware
from patentpath.api.routes import chat, documents, health, ingest, llm_status
from patentpath.config import Settings, get_settings
from patentpath.db.llm_calls import make_recorder
from patentpath.db.session import make_engine, make_sessionmaker
from patentpath.llm.gateway import build_gateway
from patentpath.llm.prompts import latest, read_prompt
from patentpath.logging_setup import setup_logging

logger = logging.getLogger("patentpath")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    engine = make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("starting", extra={"status": settings.app_env})
        worker = None

        if settings.worker_in_api:
            from patentpath.workers.main import run_embedded

            worker = asyncio.create_task(run_embedded(settings))

        yield

        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

        if app.state.queue is not None:
            await app.state.queue.close()

        await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.queue = None

    app.state.gateway = build_gateway(
        settings,
        recorder=make_recorder(app.state.sessionmaker),
    )

    app.state.system_prompt = (settings.prompts_dir / "chat_system_v1.md").read_text(
        encoding="utf-8"
    )

    classify_version = latest(settings.prompts_dir, "classify")
    app.state.classify_prompt_version = classify_version
    app.state.classify_prompt = read_prompt(
        settings.prompts_dir,
        classify_version,
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(ingest.router, prefix="/v1")
    app.include_router(llm_status.router)

    return app
