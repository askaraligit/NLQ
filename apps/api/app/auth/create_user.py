"""Create or update a workspace user without exposing a registration endpoint.

Run from apps/api after migrations, for example:
    python -m app.auth.create_user --email analyst@example.com --tenant deccan-demo
"""

from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from app.core.config import get_settings
from app.db.runtime import create_database_runtime
from app.models.application import Tenant, User
from app.services.auth_service import AuthService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update an NLQ workspace user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name")
    parser.add_argument("--tenant", required=True, help="Tenant slug from app.tenants")
    parser.add_argument("--password", help="Omit to enter it without echoing it in the shell.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = args.password or getpass.getpass("Password: ")
    normalized_email = AuthService.normalize_email(args.email)
    password_hash = AuthService.hash_password(password)
    runtime = create_database_runtime(get_settings())
    try:
        with runtime.application_sessions() as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == args.tenant))
            if tenant is None:
                raise SystemExit(f"Tenant '{args.tenant}' was not found.")
            user = session.scalar(select(User).where(User.email == normalized_email))
            if user is None:
                user = User(
                    tenant_id=tenant.id,
                    email=normalized_email,
                    display_name=args.display_name or normalized_email.split("@", 1)[0],
                    password_hash=password_hash,
                )
                session.add(user)
            else:
                user.tenant_id = tenant.id
                user.display_name = args.display_name or user.display_name
                user.password_hash = password_hash
                user.is_active = True
            session.commit()
            print(f"Workspace user ready: {normalized_email}")
    finally:
        runtime.dispose()


if __name__ == "__main__":
    main()
