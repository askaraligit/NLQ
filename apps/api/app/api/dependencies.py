"""Request-scoped access to explicitly configured runtime database services."""

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.runtime import DatabaseRuntime, analytics_session, application_session
from app.services.auth_service import (
    AuthenticatedUser,
    AuthenticationError,
    AuthService,
)

bearer_scheme = HTTPBearer(auto_error=False)


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


def get_auth_service(request: Request) -> AuthService:
    service: AuthService | None = getattr(request.app.state, "auth_service", None)
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_UNAVAILABLE", "message": "Authentication is not configured."},
        )
    return service


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: AuthService = Depends(get_auth_service),
    session: Session = Depends(get_application_session),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Sign in to continue."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return service.current_user(session, credentials.credentials)
    except AuthenticationError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Sign in to continue."},
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def get_analytics_session(request: Request) -> Generator[Session, None, None]:
    """Expose the reader identity only to future validated analytics execution services."""
    yield from analytics_session(get_database_runtime(request))
