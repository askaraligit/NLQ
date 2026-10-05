"""FastAPI bootstrap with isolated database runtime services."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.nlq import NLQAPIError, nlq_error_handler
from app.core.config import Settings, get_settings
from app.db.runtime import DatabaseConfigurationError, DatabaseRuntime, create_database_runtime
from app.services.llm_service import ProviderConfigurationError, create_llm_provider
from app.services.nlq_service import NLQService
from app.services.schema_service import SchemaService
from app.services.sql_service import QueryExecutor, SQLValidator


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
        application.state.nlq_service = None
        if runtime is not None:
            try:
                application.state.nlq_service = NLQService(
                    schema_service=SchemaService(settings.nlq_schema_max_tables),
                    provider=create_llm_provider(settings),
                    validator=SQLValidator(),
                    executor=QueryExecutor(
                        sessions=runtime.analytics_sessions,
                        timeout_ms=settings.query_timeout_ms,
                        max_rows=settings.query_max_rows,
                        max_response_bytes=settings.query_max_response_bytes,
                    ),
                )
            except ProviderConfigurationError:
                # Keep health checks independent of optional provider credentials.
                application.state.nlq_service = None
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
    application.add_exception_handler(NLQAPIError, nlq_error_handler)
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
