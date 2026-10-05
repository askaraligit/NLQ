"""Load the synthetic development fixture: python -m seeds."""

import argparse
import sys

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.config import get_migration_settings, get_migration_url
from seeds.dataset import AS_OF, SEED_VERSION
from seeds.loader import seed_database


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Load deterministic synthetic ERP data for development/test only. "
            "Uses MIGRATION_DATABASE_URL from migrations/.env or the environment. "
            "Committed seed versions are skipped; existing records are never replaced."
        )
    )
    parser.parse_args()
    engine = None
    try:
        settings = get_migration_settings()
        if settings.app_env not in {"development", "test"}:
            raise ValueError("Sample data may only be loaded with APP_ENV=development or test")
        engine = create_engine(
            get_migration_url(), hide_parameters=True, connect_args={"connect_timeout": 10}
        )
        statuses = seed_database(engine)
    except ValidationError:
        print(
            "Seed configuration invalid: check migrations/.env or environment variables.",
            file=sys.stderr,
        )
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        # Driver errors may expose connection parameters, so report an actionable safe message.
        print(
            "Seed failed; its transaction was rolled back. Check database availability, "
            "migration status, nlq_migrator permissions and existing sample data conflicts.",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print(f"Synthetic ERP fixture {SEED_VERSION}; as of {AS_OF.isoformat()}")
    for slug, status in statuses.items():
        print(f"{slug}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
