"""Authenticated NLQ history and saved-query endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_application_session, get_current_user
from app.services.auth_service import AuthenticatedUser
from app.services.workspace_service import WorkspaceNotFoundError, WorkspaceService

router = APIRouter(prefix="/nlq")


class VisualizationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    x_axis: str | None = Field(alias="xAxis")
    y_axis: str | None = Field(alias="yAxis")


class HistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    conversation_id: UUID = Field(alias="conversationId")
    question: str
    sql: str
    query_language: str = Field(alias="queryLanguage")
    summary: str
    columns: list[dict[str, str]]
    rows: list[dict[str, object]]
    visualization: VisualizationResponse
    execution_time_ms: int = Field(alias="executionTimeMs")
    created_at: datetime = Field(alias="createdAt")


class SaveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query_id: UUID = Field(alias="queryId")
    name: str = Field(min_length=1, max_length=120)


class SavedItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    query_id: UUID = Field(alias="queryId")
    name: str
    question: str
    sql: str
    visualization: VisualizationResponse
    created_at: datetime = Field(alias="createdAt")


def _workspace(request: Request) -> WorkspaceService:
    return request.app.state.workspace_service


def _history_item(record: object) -> HistoryItem:
    return HistoryItem(
        id=record.id,
        conversationId=record.conversation_id,
        question=record.question,
        sql=record.sql,
        queryLanguage=record.query_language,
        summary=record.summary,
        columns=record.columns,
        rows=record.rows,
        visualization=VisualizationResponse(**record.visualization),
        executionTimeMs=record.execution_time_ms,
        createdAt=record.created_at,
    )


def _saved_item(saved: object) -> SavedItem:
    return SavedItem(
        id=saved.id,
        queryId=saved.query_record_id,
        name=saved.name,
        question=saved.question,
        sql=saved.sql,
        visualization=VisualizationResponse(**saved.visualization),
        createdAt=saved.created_at,
    )


@router.get("/history", response_model=list[HistoryItem])
def history(
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[HistoryItem]:
    return [_history_item(record) for record in _workspace(request).history(session, user)]


@router.get("/history/{record_id}", response_model=HistoryItem)
def history_record(
    record_id: UUID,
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> HistoryItem:
    try:
        return _history_item(_workspace(request).get_record(session, user, record_id))
    except WorkspaceNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/saved", response_model=SavedItem, status_code=status.HTTP_201_CREATED)
def save_query(
    body: SaveRequest,
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> SavedItem:
    try:
        return _saved_item(_workspace(request).save(session, user, body.query_id, body.name))
    except WorkspaceNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/saved", response_model=list[SavedItem])
def saved_queries(
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[SavedItem]:
    return [_saved_item(saved) for saved in _workspace(request).saved(session, user)]


@router.delete("/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_query(
    saved_id: UUID,
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        _workspace(request).delete_saved(session, user, saved_id)
    except WorkspaceNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
