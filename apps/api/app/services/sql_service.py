"""PostgreSQL parser policy and bounded reader-role query execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from time import perf_counter
from typing import Any
from uuid import UUID

import sqlglot
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlglot import exp

from app.services.schema_service import SchemaContext


class SQLPolicyError(ValueError):
    """Generated SQL violates the application allow-list policy."""


class QueryExecutionError(RuntimeError):
    """A read-only query failed without exposing database implementation details."""


class QueryResultTooLargeError(QueryExecutionError):
    """A valid result does not fit in the configured response size."""


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: list[dict[str, Any]]
    execution_time_ms: int


_FORBIDDEN_NODE_NAMES = frozenset(
    {
        "Alter",
        "Attach",
        "Command",
        "Copy",
        "Create",
        "Delete",
        "Describe",
        "Drop",
        "Grant",
        "Insert",
        "Into",
        "Lock",
        "Merge",
        "Pragma",
        "Revoke",
        "Set",
        "Transaction",
        "TruncateTable",
        "Update",
        "Use",
    }
)
_ALLOWED_FUNCTIONS = frozenset(
    {
        "ABS",
        "AVG",
        "CAST",
        "COALESCE",
        "COUNT",
        "DATE_TRUNC",
        "EXTRACT",
        "LOWER",
        "MAX",
        "MIN",
        "NULLIF",
        "ROUND",
        "SUM",
        "TIMESTAMP_TRUNC",
        "UPPER",
    }
)


class SQLValidator:
    """Allow a deliberately small PostgreSQL SELECT subset over the supplied schema context."""

    def validate(self, sql: str, context: SchemaContext) -> str:
        candidate = sql.strip()
        if not candidate:
            raise SQLPolicyError("Generated SQL is empty.")
        if "--" in candidate or "/*" in candidate:
            raise SQLPolicyError("SQL comments are not allowed.")
        try:
            statements = sqlglot.parse(candidate, read="postgres")
        except sqlglot.errors.ParseError as error:
            raise SQLPolicyError("Generated SQL could not be parsed as PostgreSQL.") from error
        if len(statements) != 1 or statements[0] is None:
            raise SQLPolicyError("Exactly one SQL statement is required.")
        expression = statements[0]
        if not isinstance(expression, (exp.Select, exp.Union)):
            raise SQLPolicyError("Only SELECT or UNION queries are allowed.")
        if expression.args.get("with") is not None:
            raise SQLPolicyError("Common table expressions are not allowed.")
        for node in expression.walk():
            if node.__class__.__name__ in _FORBIDDEN_NODE_NAMES:
                raise SQLPolicyError("Generated SQL contains an unsupported operation.")
        tables = list(expression.find_all(exp.Table))
        if not tables:
            raise SQLPolicyError("A query must reference an approved relation.")
        aliases: dict[str, str] = {}
        for table in tables:
            table_name = table.name.lower()
            schema_name = (table.db or "").lower()
            if schema_name != context.schema_name or table_name not in context.table_names:
                raise SQLPolicyError(
                    "Generated SQL references a relation outside the approved context."
                )
            aliases[table.alias_or_name.lower()] = table_name
        for star in expression.find_all(exp.Star):
            if not isinstance(star.parent, exp.Count):
                raise SQLPolicyError("SELECT * is not allowed.")
        self._validate_columns(expression, aliases, context)
        self._validate_functions(expression)
        return expression.sql(dialect="postgres")

    @staticmethod
    def _validate_columns(
        expression: exp.Expression, aliases: dict[str, str], context: SchemaContext
    ) -> None:
        all_columns = frozenset().union(*(context.column_names(name) for name in aliases.values()))
        for column in expression.find_all(exp.Column):
            column_name = column.name.lower()
            if column_name not in all_columns:
                raise SQLPolicyError("Generated SQL references an unknown column.")
            qualifier = column.table.lower() if column.table else ""
            if qualifier:
                table_name = aliases.get(qualifier)
                if table_name is None or column_name not in context.column_names(table_name):
                    raise SQLPolicyError(
                        "Generated SQL uses a column with an invalid table qualifier."
                    )

    @staticmethod
    def _validate_functions(expression: exp.Expression) -> None:
        for function in expression.find_all(exp.Func):
            name = function.sql_name().upper()
            if name not in _ALLOWED_FUNCTIONS:
                raise SQLPolicyError(
                    "Generated SQL uses a function outside the approved allow-list."
                )


class QueryExecutor:
    """Execute only already validated SQL with independent time, row, and byte limits."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        timeout_ms: int,
        max_rows: int,
        max_response_bytes: int,
    ) -> None:
        self.sessions = sessions
        self.timeout_ms = timeout_ms
        self.max_rows = max_rows
        self.max_response_bytes = max_response_bytes

    def execute(self, validated_sql: str) -> QueryResult:
        # The outer LIMIT prevents an unrestricted result from reaching the response serializer.
        bounded_sql = f"SELECT * FROM ({validated_sql}) AS nlq_result LIMIT :row_limit"
        started = perf_counter()
        try:
            with self.sessions() as session:
                with session.begin():
                    session.execute(text("SET TRANSACTION READ ONLY"))
                    session.execute(
                        text("SELECT set_config('statement_timeout', :timeout, true)"),
                        {"timeout": f"{self.timeout_ms}ms"},
                    )
                    result = session.execute(text(bounded_sql), {"row_limit": self.max_rows})
                    columns = tuple(result.keys())
                    rows = self._normalize_rows(result.mappings().all())
        except SQLAlchemyError as error:
            raise QueryExecutionError("The validated query could not be executed.") from error
        elapsed_ms = round((perf_counter() - started) * 1000)
        return QueryResult(columns=columns, rows=rows, execution_time_ms=elapsed_ms)

    def _normalize_rows(self, rows: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        response_size = 0
        for row in rows:
            item = {str(key): self._normalize_value(value) for key, value in row.items()}
            response_size += len(
                json.dumps(item, separators=(",", ":"), ensure_ascii=False).encode()
            )
            if response_size > self.max_response_bytes:
                raise QueryResultTooLargeError(
                    "The query result exceeds the configured response limit."
                )
            normalized.append(item)
        return normalized

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        return value
