"""HTTP boundary for the safe natural-language query workflow."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_application_session, get_current_user
from app.services.auth_service import AuthenticatedUser
from app.services.llm_service import ProviderResponseError
from app.services.nlq_service import NLQService
from app.services.sql_service import QueryExecutionError, QueryResultTooLargeError, SQLPolicyError
from app.services.workspace_service import WorkspaceNotFoundError, WorkspaceService

router = APIRouter(prefix="/nlq")


class QueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(min_length=3, max_length=1_000)
    conversation_id: UUID | None = Field(default=None, alias="conversationId")


class ResultColumn(BaseModel):
    name: str


class VisualizationResponse(BaseModel):
    type: str
    x_axis: str | None = Field(default=None, alias="xAxis")
    y_axis: str | None = Field(default=None, alias="yAxis")


class QueryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query_id: UUID = Field(alias="queryId")
    conversation_id: UUID = Field(alias="conversationId")
    question: str
    sql: str
    columns: list[ResultColumn]
    rows: list[dict[str, object]]
    summary: str
    visualization: VisualizationResponse
    execution_time_ms: int = Field(alias="executionTimeMs")


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class NLQAPIError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def nlq_error_handler(_: Request, error: NLQAPIError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )


def _get_service(request: Request) -> NLQService:
    service: NLQService | None = getattr(request.app.state, "nlq_service", None)
    if service is None:
        raise NLQAPIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "NLQ_UNAVAILABLE",
            "NLQ querying is unavailable until its database and provider configuration are ready.",
        )
    return service


def _workspace(request: Request) -> WorkspaceService:
    return request.app.state.workspace_service


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Generate, validate, and execute one read-only ERP analytics query",
)
async def query(
    request: Request,
    body: QueryRequest,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> QueryResponse:
    service = _get_service(request)
    try:
        conversation, prior_turns = _workspace(request).prepare_conversation(
            session, user, body.conversation_id, body.question
        )
        result = await service.query(body.question, prior_turns)
        _workspace(request).record_query(session, user, conversation, body.question, result)
    except WorkspaceNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ProviderResponseError as error:
        raise NLQAPIError(
            status.HTTP_502_BAD_GATEWAY,
            "PROVIDER_UNAVAILABLE",
            "The query provider could not respond.",
        ) from error
    except SQLPolicyError as error:
        raise NLQAPIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "UNSAFE_GENERATED_SQL",
            "The generated query did not pass the SQL safety policy.",
        ) from error
    except QueryResultTooLargeError as error:
        raise NLQAPIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "QUERY_RESULT_TOO_LARGE",
            "The query result exceeds the configured response limit.",
        ) from error
    except QueryExecutionError as error:
        raise NLQAPIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "QUERY_EXECUTION_FAILED",
            "The query could not be executed against the analytics database.",
        ) from error
    return QueryResponse(
        query_id=result.query_id,
        conversation_id=conversation.id,
        question=body.question,
        sql=result.sql,
        columns=[ResultColumn(name=column) for column in result.columns],
        rows=result.rows,
        summary=result.summary,
        visualization=VisualizationResponse(
            type=result.visualization_type, xAxis=result.x_axis, yAxis=result.y_axis
        ),
        execution_time_ms=result.execution_time_ms,
    )
