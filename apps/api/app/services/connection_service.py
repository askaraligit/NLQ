"""Encrypted PostgreSQL and MongoDB connection records with bounded schema discovery."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.application import DataConnection
from app.services.auth_service import AuthenticatedUser
from app.services.mongo_service import MongoQueryExecutor
from app.services.schema_service import SchemaColumn, SchemaContext, SchemaRelationship, SchemaTable
from app.services.sql_service import QueryExecutor

_schema_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")
_database_pattern = re.compile(r'^[^/\\.$"\x00]{1,63}$')
_source_types = frozenset({"postgresql", "mongodb"})


class ConnectionConfigurationError(RuntimeError):
    """Encryption is unavailable or a connection URL is unacceptable."""


class ConnectionUnavailableError(RuntimeError):
    """A user connection cannot be reached or inspected."""


class ConnectionNotFoundError(RuntimeError):
    """A connection is absent or owned by another user."""


@dataclass(frozen=True)
class OpenConnection:
    engine: Engine
    sessions: sessionmaker[Session]
    schema_service: ExternalSchemaService

    def dispose(self) -> None:
        self.engine.dispose()


@dataclass(frozen=True)
class OpenMongoConnection:
    client: MongoClient[Any]
    database: Database[Any]
    schema_service: MongoSchemaService

    def dispose(self) -> None:
        self.client.close()


class ExternalSchemaService:
    def __init__(self, engine: Engine, schema_name: str, max_tables: int) -> None:
        self.engine = engine
        self.schema_name = schema_name
        self.max_tables = max_tables
        self.catalog, self.relationships = self._inspect()

    def _inspect(self) -> tuple[dict[str, SchemaTable], tuple[SchemaRelationship, ...]]:
        try:
            inspector = inspect(self.engine)
            names = inspector.get_table_names(schema=self.schema_name)[:50]
            catalog: dict[str, SchemaTable] = {}
            relationships: list[SchemaRelationship] = []
            for name in names:
                columns = inspector.get_columns(name, schema=self.schema_name)
                catalog[name] = SchemaTable(
                    name=name,
                    description=f"Table {self.schema_name}.{name}.",
                    columns=tuple(
                        SchemaColumn(
                            name=str(column["name"]),
                            data_type=str(column["type"]),
                            nullable=bool(column.get("nullable", True)),
                        )
                        for column in columns
                    ),
                    keywords=tuple(name.lower().split("_")),
                )
                for foreign_key in inspector.get_foreign_keys(name, schema=self.schema_name):
                    target_schema = foreign_key.get("referred_schema") or self.schema_name
                    target_table = foreign_key.get("referred_table")
                    source_columns = foreign_key.get("constrained_columns") or []
                    target_columns = foreign_key.get("referred_columns") or []
                    if target_schema != self.schema_name or target_table not in names:
                        continue
                    for source, target in zip(source_columns, target_columns, strict=True):
                        relationships.append(
                            SchemaRelationship(name, str(source), str(target_table), str(target))
                        )
        except SQLAlchemyError as error:
            raise ConnectionUnavailableError(
                "The database schema could not be inspected."
            ) from error
        if not catalog:
            raise ConnectionUnavailableError(
                "The selected schema does not contain accessible tables."
            )
        return catalog, tuple(relationships)

    def context_for(self, question: str) -> SchemaContext:
        return _context_for(
            question, self.schema_name, self.catalog, self.relationships, self.max_tables
        )


class MongoSchemaService:
    """Discover collection and top-level field names without retaining document values."""

    def __init__(self, database: Database[Any], max_tables: int) -> None:
        self.database = database
        self.schema_name = database.name
        self.max_tables = max_tables
        self.catalog = self._inspect()

    def _inspect(self) -> dict[str, SchemaTable]:
        try:
            names = [
                name
                for name in self.database.list_collection_names()
                if not name.startswith("system.")
            ][:50]
            catalog: dict[str, SchemaTable] = {}
            for name in names:
                fields: dict[str, str] = {"_id": "ObjectId"}
                for document in self.database[name].find({}, projection=None, limit=50):
                    for field, value in document.items():
                        fields.setdefault(str(field), type(value).__name__)
                catalog[name] = SchemaTable(
                    name=name,
                    description=f"MongoDB collection {name} in database {self.schema_name}.",
                    columns=tuple(
                        SchemaColumn(name=field, data_type=data_type, nullable=True)
                        for field, data_type in sorted(fields.items())
                    ),
                    keywords=tuple(name.lower().split("_")),
                )
        except PyMongoError as error:
            raise ConnectionUnavailableError(
                "The MongoDB database could not be inspected."
            ) from error
        if not catalog:
            raise ConnectionUnavailableError(
                "The selected MongoDB database has no accessible collections."
            )
        return catalog

    def context_for(self, question: str) -> SchemaContext:
        return _context_for(question, self.schema_name, self.catalog, (), self.max_tables)


def _context_for(
    question: str,
    schema_name: str,
    catalog: dict[str, SchemaTable],
    relationships: tuple[SchemaRelationship, ...],
    max_tables: int,
) -> SchemaContext:
    tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    ranked = sorted(
        (
            (len(tokens & (set(table.name.lower().split("_")) | set(table.keywords))), table.name)
            for table in catalog.values()
        ),
        key=lambda item: (-item[0], item[1]),
    )
    selected = [name for score, name in ranked if score > 0][:max_tables]
    if not selected:
        selected = [name for _, name in ranked[:max_tables]]
    selected_set = set(selected)
    return SchemaContext(
        schema_name=schema_name,
        tables=tuple(catalog[name] for name in selected),
        relationships=tuple(
            relation
            for relation in relationships
            if relation.source_table in selected_set and relation.target_table in selected_set
        ),
        business_rules=(
            "Use only collections and fields in this approved schema context.",
            "Do not infer data that is not present in the result.",
        ),
    )


class ConnectionService:
    def __init__(self, settings: Settings) -> None:
        if settings.connection_encryption_key is None:
            raise ConnectionConfigurationError("CONNECTION_ENCRYPTION_KEY is not configured.")
        try:
            self.cipher = Fernet(settings.connection_encryption_key.get_secret_value().encode())
        except (TypeError, ValueError) as error:
            raise ConnectionConfigurationError("CONNECTION_ENCRYPTION_KEY is invalid.") from error
        self.max_tables = settings.nlq_schema_max_tables
        self.timeout_seconds = settings.database_pool_timeout_seconds
        self.query_timeout_ms = settings.query_timeout_ms
        self.query_max_rows = settings.query_max_rows
        self.query_max_response_bytes = settings.query_max_response_bytes

    @staticmethod
    def _postgres_url(value: str) -> URL:
        try:
            url = make_url(value.strip())
        except Exception as error:
            raise ConnectionConfigurationError(
                "Enter a valid PostgreSQL connection URL."
            ) from error
        if (
            url.get_backend_name() != "postgresql"
            or not url.username
            or not url.password
            or not url.host
            or not url.database
        ):
            raise ConnectionConfigurationError(
                "Use a complete PostgreSQL URL with host, database, username, and password."
            )
        return url.set(drivername="postgresql+psycopg")

    @staticmethod
    def _mongo_url(value: str) -> str:
        url = value.strip()
        if not url.startswith(("mongodb://", "mongodb+srv://")) or any(
            char.isspace() for char in url
        ):
            raise ConnectionConfigurationError("Enter a valid MongoDB connection URI.")
        return url

    @staticmethod
    def _schema(schema_name: str) -> str:
        if not _schema_pattern.fullmatch(schema_name):
            raise ConnectionConfigurationError(
                "Schema names may contain only letters, numbers, and underscores."
            )
        return schema_name

    @staticmethod
    def _database(database_name: str | None) -> str:
        candidate = (database_name or "").strip()
        if not _database_pattern.fullmatch(candidate):
            raise ConnectionConfigurationError("Enter a valid MongoDB database name.")
        return candidate

    def _engine(self, url: URL) -> Engine:
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            pool_timeout=self.timeout_seconds,
            hide_parameters=True,
            connect_args={"connect_timeout": self.timeout_seconds},
        )

    def _mongo_client(self, url: str) -> MongoClient[Any]:
        return MongoClient(
            url,
            serverSelectionTimeoutMS=self.timeout_seconds * 1000,
            connectTimeoutMS=self.timeout_seconds * 1000,
            socketTimeoutMS=self.timeout_seconds * 1000,
            serverMonitoringMode="poll",
        )

    def add(
        self,
        session: Session,
        user: AuthenticatedUser,
        name: str,
        raw_url: str,
        schema_name: str = "public",
        source_type: str = "postgresql",
        database_name: str | None = None,
    ) -> DataConnection:
        source_type = source_type.lower().strip()
        if source_type not in _source_types:
            raise ConnectionConfigurationError("Select PostgreSQL or MongoDB as the source type.")
        if not name.strip():
            raise ConnectionConfigurationError("Connection name is required.")
        if source_type == "postgresql":
            stored_url, schema_name, database_name = self._add_postgres(raw_url, schema_name)
        else:
            stored_url, schema_name, database_name = self._add_mongo(raw_url, database_name)
        session.query(DataConnection).filter(DataConnection.user_id == user.id).update(
            {DataConnection.is_active: False}
        )
        record = DataConnection(
            user_id=user.id,
            name=name.strip(),
            encrypted_url=self.cipher.encrypt(stored_url.encode()).decode(),
            source_type=source_type,
            schema_name=schema_name,
            database_name=database_name,
            is_active=True,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    def _add_postgres(self, raw_url: str, schema_name: str) -> tuple[str, str, None]:
        url = self._postgres_url(raw_url)
        schema_name = self._schema(schema_name)
        engine = self._engine(url)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            ExternalSchemaService(engine, schema_name, self.max_tables)
        except ConnectionUnavailableError:
            raise
        except SQLAlchemyError as error:
            raise ConnectionUnavailableError(
                "The database could not be reached with those credentials."
            ) from error
        finally:
            engine.dispose()
        return url.render_as_string(hide_password=False), schema_name, None

    def _add_mongo(self, raw_url: str, database_name: str | None) -> tuple[str, str, str]:
        url = self._mongo_url(raw_url)
        database_name = self._database(database_name)
        client = self._mongo_client(url)
        try:
            client.admin.command({"ping": 1})
            MongoSchemaService(client[database_name], self.max_tables)
        except ConnectionUnavailableError:
            raise
        except PyMongoError as error:
            raise ConnectionUnavailableError(
                "The MongoDB database could not be reached with those credentials."
            ) from error
        finally:
            client.close()
        return url, database_name, database_name

    @staticmethod
    def list(session: Session, user: AuthenticatedUser) -> list[DataConnection]:
        return list(session.query(DataConnection).filter(DataConnection.user_id == user.id).all())

    @staticmethod
    def get(session: Session, user: AuthenticatedUser, connection_id: UUID) -> DataConnection:
        record = session.get(DataConnection, connection_id)
        if record is None or record.user_id != user.id:
            raise ConnectionNotFoundError("Connection not found.")
        return record

    def activate(
        self, session: Session, user: AuthenticatedUser, connection_id: UUID
    ) -> DataConnection:
        record = self.get(session, user, connection_id)
        session.query(DataConnection).filter(DataConnection.user_id == user.id).update(
            {DataConnection.is_active: False}
        )
        record.is_active = True
        session.commit()
        session.refresh(record)
        return record

    def delete(self, session: Session, user: AuthenticatedUser, connection_id: UUID) -> None:
        record = self.get(session, user, connection_id)
        session.delete(record)
        session.commit()

    def _decrypt(self, record: DataConnection) -> str:
        try:
            return self.cipher.decrypt(record.encrypted_url.encode()).decode()
        except (InvalidToken, UnicodeDecodeError) as error:
            raise ConnectionUnavailableError(
                "The connection credentials could not be read."
            ) from error

    @contextmanager
    def open_active(
        self, session: Session, user: AuthenticatedUser
    ) -> Iterator[OpenConnection | OpenMongoConnection | None]:
        record = (
            session.query(DataConnection)
            .filter(DataConnection.user_id == user.id, DataConnection.is_active.is_(True))
            .one_or_none()
        )
        if record is None:
            yield None
            return
        url = self._decrypt(record)
        if record.source_type == "mongodb":
            database_name = self._database(record.database_name)
            client = self._mongo_client(url)
            source: OpenMongoConnection | None = None
            try:
                client.admin.command({"ping": 1})
                database = client[database_name]
                source = OpenMongoConnection(
                    client, database, MongoSchemaService(database, self.max_tables)
                )
                yield source
            except ConnectionUnavailableError:
                raise
            except PyMongoError as error:
                raise ConnectionUnavailableError(
                    "The active MongoDB connection could not be reached."
                ) from error
            finally:
                if source is None:
                    client.close()
                else:
                    source.dispose()
            return
        engine: Engine | None = None
        source: OpenConnection | None = None
        try:
            engine = self._engine(self._postgres_url(url))
            source = OpenConnection(
                engine=engine,
                sessions=sessionmaker(bind=engine, expire_on_commit=False),
                schema_service=ExternalSchemaService(engine, record.schema_name, self.max_tables),
            )
            yield source
        except ConnectionUnavailableError:
            raise
        except SQLAlchemyError as error:
            raise ConnectionUnavailableError(
                "The active data connection could not be reached."
            ) from error
        finally:
            if source is not None:
                source.dispose()
            elif engine is not None:
                engine.dispose()

    def executor(self, source: OpenConnection) -> QueryExecutor:
        return QueryExecutor(
            sessions=source.sessions,
            timeout_ms=self.query_timeout_ms,
            max_rows=self.query_max_rows,
            max_response_bytes=self.query_max_response_bytes,
        )

    def mongo_executor(self, source: OpenMongoConnection) -> MongoQueryExecutor:
        return MongoQueryExecutor(
            database=source.database,
            timeout_ms=self.query_timeout_ms,
            max_response_bytes=self.query_max_response_bytes,
        )
