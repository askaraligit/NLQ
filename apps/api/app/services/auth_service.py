"""Password authentication and signed access-token helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.application import User

_password_hash = PasswordHash.recommended()
_algorithm = "HS256"


class AuthenticationError(RuntimeError):
    """Credentials are missing, invalid, expired, or no longer active."""


class AuthenticationConfigurationError(RuntimeError):
    """The server cannot safely issue or verify tokens."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str
    display_name: str
    tenant_id: UUID


class AuthService:
    def __init__(self, settings: Settings) -> None:
        if settings.jwt_secret is None or len(settings.jwt_secret.get_secret_value()) < 32:
            raise AuthenticationConfigurationError(
                "JWT_SECRET must contain at least 32 characters."
            )
        self.secret = settings.jwt_secret.get_secret_value()
        self.issuer = settings.jwt_issuer
        self.audience = settings.jwt_audience
        self.expiry = timedelta(minutes=settings.jwt_access_token_minutes)

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    def authenticate(self, session: Session, email: str, password: str) -> User:
        user = session.scalar(select(User).where(User.email == self.normalize_email(email)))
        if (
            user is None
            or not user.is_active
            or not _password_hash.verify(password, user.password_hash)
        ):
            raise AuthenticationError("Incorrect email or password.")
        return user

    def issue_token(self, user: User) -> tuple[str, int]:
        now = datetime.now(UTC)
        expires_at = now + self.expiry
        token = jwt.encode(
            {
                "sub": str(user.id),
                "iss": self.issuer,
                "aud": self.audience,
                "iat": now,
                "exp": expires_at,
                "jti": str(uuid4()),
            },
            self.secret,
            algorithm=_algorithm,
        )
        return token, int(self.expiry.total_seconds())

    def current_user(self, session: Session, token: str) -> AuthenticatedUser:
        try:
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=[_algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["sub", "exp", "iat", "iss", "aud"]},
            )
            user_id = UUID(str(claims["sub"]))
        except (jwt.PyJWTError, ValueError, KeyError) as error:
            raise AuthenticationError("Your session is invalid or has expired.") from error
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Your session is invalid or has expired.")
        return AuthenticatedUser(user.id, user.email, user.display_name, user.tenant_id)

    @staticmethod
    def hash_password(password: str) -> str:
        if len(password) < 12:
            raise ValueError("Password must contain at least 12 characters.")
        return _password_hash.hash(password)
