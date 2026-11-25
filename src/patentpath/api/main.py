"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from patentpath.api.errors import (
    http_exception_handler,
    validation_exception_handler,
)
from patentpath.api.middleware import RequestLoggingMiddleware
from patentpath.api.routes import chat, documents, health
from patentpath.config import Settings, get_settings
from patentpath.db.llm_calls import make_recorder
from patentpath.db.session import AsyncSessionLocal, engine
from patentpath.llm.gateway import build_gateway
from patentpath.logging_setup import setup_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.state.gateway = build_gateway(
        settings,
        recorder=make_recorder(AsyncSessionLocal),
    )
    app.state.system_prompt = (settings.prompts_dir / "chat_system_v1.md").read_text(
        encoding="utf-8"
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(404, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)

    return app
