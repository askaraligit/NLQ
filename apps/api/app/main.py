"""FastAPI bootstrap with isolated database runtime services."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.db.runtime import DatabaseConfigurationError, DatabaseRuntime, create_database_runtime


def create_app(
    settings: Settings | None = None, database_runtime: DatabaseRuntime | None = None
) -> FastAPI:
    settings = settings if settings is not None else get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime = database_runtime
        if runtime is None:
            try:
                runtime = create_database_runtime(settings)
            except DatabaseConfigurationError:
                # Liveness stays available while readiness reports missing/malformed runtime config.
                runtime = None
        application.state.database_runtime = runtime
        try:
            yield
        finally:
            if runtime is not None:
                runtime.dispose()

    application = FastAPI(
        title="NLQ API",
        description=(
            "API foundation with separate application and analytics database runtime paths."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(api_router)
    return application


app = create_app()
