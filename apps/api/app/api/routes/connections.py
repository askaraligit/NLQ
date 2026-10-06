"""Authenticated user-managed PostgreSQL and MongoDB data connections."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_application_session, get_current_user
from app.services.auth_service import AuthenticatedUser
from app.services.connection_service import (
    ConnectionConfigurationError,
    ConnectionNotFoundError,
    ConnectionService,
    ConnectionUnavailableError,
)

router = APIRouter(prefix="/connections")


class ConnectionCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=120)
    connection_url: str = Field(alias="connectionUrl", min_length=16, max_length=4_000)
    source_type: str = Field(
        default="postgresql", alias="sourceType", pattern="^(postgresql|mongodb)$"
    )
    schema_name: str = Field(default="public", alias="schemaName", min_length=1, max_length=63)
    database_name: str | None = Field(default=None, alias="databaseName", max_length=63)


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    name: str
    source_type: str = Field(alias="sourceType")
    schema_name: str = Field(alias="schemaName")
    database_name: str | None = Field(alias="databaseName")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")


def _service(request: Request) -> ConnectionService:
    service: ConnectionService | None = getattr(request.app.state, "connection_service", None)
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONNECTIONS_UNAVAILABLE",
                "message": "Database connections are not configured on this server.",
            },
        )
    return service


def _response(record: object) -> ConnectionResponse:
    return ConnectionResponse(
        id=record.id,
        name=record.name,
        sourceType=record.source_type,
        schemaName=record.schema_name,
        databaseName=record.database_name,
        isActive=record.is_active,
        createdAt=record.created_at,
    )


@router.get("", response_model=list[ConnectionResponse])
def list_connections(
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[ConnectionResponse]:
    return [_response(record) for record in _service(request).list(session, user)]


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(
    body: ConnectionCreateRequest,
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ConnectionResponse:
    try:
        return _response(
            _service(request).add(
                session,
                user,
                body.name,
                body.connection_url,
                body.schema_name,
                body.source_type,
                body.database_name,
            )
        )
    except ConnectionConfigurationError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except ConnectionUnavailableError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post("/{connection_id}/activate", response_model=ConnectionResponse)
def activate_connection(
    connection_id: UUID,
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ConnectionResponse:
    try:
        return _response(_service(request).activate(session, user, connection_id))
    except ConnectionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: UUID,
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        _service(request).delete(session, user, connection_id)
    except ConnectionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
