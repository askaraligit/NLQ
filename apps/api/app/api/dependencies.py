"""Request-scoped access to explicitly configured runtime database services."""

from collections.abc import Generator

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.runtime import DatabaseRuntime, analytics_session, application_session


def get_database_runtime(request: Request) -> DatabaseRuntime:
    runtime: DatabaseRuntime | None = getattr(request.app.state, "database_runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database runtime is not configured.",
        )
    return runtime


def get_application_session(request: Request) -> Generator[Session, None, None]:
    """Expose the application identity only to future application repositories."""
    yield from application_session(get_database_runtime(request))


def get_analytics_session(request: Request) -> Generator[Session, None, None]:
    """Expose the reader identity only to future validated analytics execution services."""
    yield from analytics_session(get_database_runtime(request))
