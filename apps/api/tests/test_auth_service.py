"""Focused coverage for Phase 7 password and token boundaries."""

from uuid import UUID

import pytest

from app.core.config import Settings
from app.models.application import User
from app.services.auth_service import (
    AuthenticationConfigurationError,
    AuthenticationError,
    AuthService,
)


class UserSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def get(self, _: type[User], __: UUID) -> User | None:
        return self.user


def test_auth_service_issues_and_verifies_an_expiring_subject_token() -> None:
    service = AuthService(Settings(jwt_secret="a" * 32, _env_file=None))
    user = User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        tenant_id=UUID("00000000-0000-0000-0000-000000000002"),
        email="analyst@example.com",
        display_name="Analyst",
        password_hash=AuthService.hash_password("a secure test password"),
        is_active=True,
    )

    token, expiry = service.issue_token(user)
    current = service.current_user(UserSession(user), token)

    assert expiry == 3_600
    assert current.id == user.id
    assert current.email == "analyst@example.com"


def test_auth_service_rejects_short_signing_secret_and_invalid_token() -> None:
    with pytest.raises(AuthenticationConfigurationError):
        AuthService(Settings(jwt_secret="too-short", _env_file=None))

    service = AuthService(Settings(jwt_secret="b" * 32, _env_file=None))
    with pytest.raises(AuthenticationError):
        service.current_user(UserSession(None), "invalid")
