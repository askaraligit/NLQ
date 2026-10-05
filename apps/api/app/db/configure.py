"""Create missing local database credentials without replacing existing configuration."""

import argparse
import secrets
import sys
from pathlib import Path

from dotenv import dotenv_values, set_key
from sqlalchemy.engine import URL

from app.db.config import API_DIRECTORY


def _local_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Configuration paths must remain inside the repository")
    return path


def _set_if_missing(path: Path, key: str, value: str) -> bool:
    if dotenv_values(path, interpolate=False).get(key):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    set_key(path, key, value, quote_mode="always")
    return True


def configure_environment(root: Path) -> list[str]:
    root = root.resolve()
    if not (root / "apps/api/pyproject.toml").is_file() or not (root / ".env.example").is_file():
        raise ValueError("Choose the NLQ repository root")
    files = {
        "root": _local_file(root, ".env"),
        "runtime": _local_file(root, "apps/api/.env"),
        "migration": _local_file(root, "apps/api/migrations/.env"),
    }
    if not files["root"].is_file() or not files["runtime"].is_file():
        raise ValueError("Run scripts/setup.ps1 before configuring database credentials")
    values = dotenv_values(files["root"], interpolate=False)
    if not values.get("POSTGRES_PASSWORD"):
        raise ValueError("Set POSTGRES_PASSWORD in the root .env first")
    if values.get("POSTGRES_HOST") not in (None, "", "localhost", "127.0.0.1", "::1"):
        raise ValueError("Local environment setup only supports a loopback PostgreSQL host")
    port = int(values.get("POSTGRES_PORT") or "5432")
    if not 1 <= port <= 65535:
        raise ValueError("POSTGRES_PORT must be between 1 and 65535")
    database = values.get("POSTGRES_DB") or "nlq"
    changed = []
    for role in ("app", "reader", "migrator"):
        key = f"NLQ_{role.upper()}_PASSWORD"
        password = values.get(key) or secrets.token_hex(32)
        if len(password) < 16:
            raise ValueError("Database role passwords must contain at least 16 characters")
        if _set_if_missing(files["root"], key, password):
            changed.append(key)
        url = URL.create(
            "postgresql+psycopg",
            username=f"nlq_{role}",
            password=password,
            host=values.get("POSTGRES_HOST") or "127.0.0.1",
            port=port,
            database=database,
        ).render_as_string(hide_password=False)
        target = files["migration"] if role == "migrator" else files["runtime"]
        target_key = {
            "app": "DATABASE_URL",
            "reader": "ANALYTICS_DATABASE_URL",
            "migrator": "MIGRATION_DATABASE_URL",
        }[role]
        if _set_if_missing(target, target_key, url):
            changed.append(target_key)
    if _set_if_missing(files["migration"], "APP_ENV", "development"):
        changed.append("migration APP_ENV")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=API_DIRECTORY.parent.parent)
    args = parser.parse_args()
    try:
        changed = configure_environment(args.root)
    except (OSError, ValueError):
        print(
            "Local database configuration failed. Check repository paths and .env settings.",
            file=sys.stderr,
        )
        return 1
    print(f"Local database configuration ready ({len(changed)} missing settings added).")
    print("Existing nonempty settings were preserved. No credentials were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
