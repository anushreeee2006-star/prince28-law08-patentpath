"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from patentpath.api.errors import (
    http_exception_handler,
    validation_exception_handler,
)
from patentpath.api.middleware import RequestLoggingMiddleware
from patentpath.api.routes import documents, health
from patentpath.config import Settings, get_settings
from patentpath.logging_setup import setup_logging
from patentpath.store import RecordStore


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = RecordStore(settings.data_file)
        store.load()
        app.state.store = store
        yield

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(404, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    app.include_router(health.router)
    app.include_router(documents.router)

    return app
