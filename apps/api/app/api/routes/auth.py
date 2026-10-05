"""Session login and current-user preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_application_session, get_auth_service, get_current_user
from app.services.auth_service import AuthenticatedUser, AuthenticationError, AuthService
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/auth")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    email: str
    display_name: str = Field(alias="displayName")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1_024)


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    expires_in: int = Field(alias="expiresIn")
    user: UserResponse


class SettingsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    preferred_page_size: int = Field(alias="preferredPageSize")
    compact_tables: bool = Field(alias="compactTables")


class SettingsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    preferred_page_size: int = Field(alias="preferredPageSize", ge=10, le=100)
    compact_tables: bool = Field(alias="compactTables")


def _workspace(request: Request) -> WorkspaceService:
    return request.app.state.workspace_service


def _user_response(user: AuthenticatedUser) -> UserResponse:
    return UserResponse(id=str(user.id), email=user.email, displayName=user.display_name)


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    session: Session = Depends(get_application_session),
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    try:
        user = service.authenticate(session, body.email, body.password)
    except AuthenticationError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password."
        ) from error
    token, expires_in = service.issue_token(user)
    return LoginResponse(
        accessToken=token,
        expiresIn=expires_in,
        user=UserResponse(id=str(user.id), email=user.email, displayName=user.display_name),
    )


@router.get("/me", response_model=UserResponse)
def me(user: AuthenticatedUser = Depends(get_current_user)) -> UserResponse:
    return _user_response(user)


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> SettingsResponse:
    settings = _workspace(request).settings(session, user)
    return SettingsResponse(
        preferredPageSize=settings.preferred_page_size, compactTables=settings.compact_tables
    )


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    body: SettingsRequest,
    request: Request,
    session: Session = Depends(get_application_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> SettingsResponse:
    if body.preferred_page_size not in {10, 25, 50, 100}:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a supported page size."
        )
    settings = _workspace(request).settings(session, user)
    settings.preferred_page_size = body.preferred_page_size
    settings.compact_tables = body.compact_tables
    session.commit()
    return SettingsResponse(
        preferredPageSize=settings.preferred_page_size, compactTables=settings.compact_tables
    )
