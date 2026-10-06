"""Read-only MongoDB aggregation validation and bounded execution."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from time import perf_counter
from typing import Any
from uuid import UUID

from bson import Decimal128, ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.services.schema_service import SchemaContext
from app.services.sql_service import QueryResult, QueryResultTooLargeError


class MongoPolicyError(ValueError):
    """Generated MongoDB aggregation violates the read-only allow-list."""


class MongoQueryExecutionError(RuntimeError):
    """A validated MongoDB aggregation could not be completed."""


_ALLOWED_STAGES = frozenset(
    {"$match", "$project", "$group", "$sort", "$limit", "$unwind", "$count"}
)
_FORBIDDEN_OPERATORS = frozenset(
    {"$where", "$function", "$accumulator", "$out", "$merge", "$unionWith", "$lookup"}
)


class MongoPipelineValidator:
    """Accept a small aggregation-pipeline subset over discovered collections only."""

    def __init__(self, max_rows: int) -> None:
        self.max_rows = max_rows

    def validate(
        self, collection: str, pipeline: list[dict[str, object]], context: SchemaContext
    ) -> tuple[str, list[dict[str, object]]]:
        if collection not in context.table_names:
            raise MongoPolicyError("The collection is outside the approved context.")
        if not pipeline or len(pipeline) > 12:
            raise MongoPolicyError(
                "An aggregation pipeline must contain between one and twelve stages."
            )
        fields = context.column_names(collection)
        validated: list[dict[str, object]] = []
        for stage in pipeline:
            if not isinstance(stage, dict) or len(stage) != 1:
                raise MongoPolicyError("Each aggregation stage must contain exactly one operation.")
            operator, body = next(iter(stage.items()))
            if operator in _FORBIDDEN_OPERATORS or operator not in _ALLOWED_STAGES:
                raise MongoPolicyError("The aggregation uses an unsupported operation.")
            if operator == "$limit":
                if (
                    not isinstance(body, int)
                    or isinstance(body, bool)
                    or not 1 <= body <= self.max_rows
                ):
                    raise MongoPolicyError(
                        "A pipeline limit must be within the configured row limit."
                    )
            elif not isinstance(body, (dict, str)):
                raise MongoPolicyError("The aggregation stage has an invalid value.")
            self._validate_expression(
                body,
                fields,
                allow_output_names=operator in {"$group", "$project", "$count"},
            )
            validated.append({operator: body})
        if not any("$limit" in stage for stage in validated):
            validated.append({"$limit": self.max_rows})
        return collection, validated

    def _validate_expression(
        self, value: object, fields: frozenset[str], *, allow_output_names: bool = False
    ) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise MongoPolicyError("Aggregation keys must be strings.")
                if key in _FORBIDDEN_OPERATORS:
                    raise MongoPolicyError("The aggregation uses a forbidden operation.")
                if key.startswith("$") and key not in {
                    "$and",
                    "$or",
                    "$nor",
                    "$not",
                    "$eq",
                    "$ne",
                    "$gt",
                    "$gte",
                    "$lt",
                    "$lte",
                    "$in",
                    "$nin",
                    "$exists",
                    "$regex",
                    "$sum",
                    "$avg",
                    "$min",
                    "$max",
                    "$first",
                    "$last",
                    "$push",
                    "$addToSet",
                    "$year",
                    "$month",
                    "$dayOfMonth",
                    "$dateToString",
                    "$cond",
                    "$ifNull",
                    "$size",
                }:
                    raise MongoPolicyError("The aggregation uses an unsupported operator.")
                if not key.startswith("$") and not allow_output_names:
                    self._validate_field(key, fields)
                self._validate_expression(child, fields, allow_output_names=allow_output_names)
        elif isinstance(value, list):
            for item in value:
                self._validate_expression(item, fields, allow_output_names=allow_output_names)
        elif isinstance(value, str) and value.startswith("$"):
            self._validate_field(value[1:], fields)

    @staticmethod
    def _validate_field(value: str, fields: frozenset[str]) -> None:
        root = value.split(".", 1)[0]
        if root and root != "_id" and root not in fields:
            raise MongoPolicyError("The aggregation references an unknown field.")


class MongoQueryExecutor:
    def __init__(self, database: Database[Any], timeout_ms: int, max_response_bytes: int) -> None:
        self.database = database
        self.timeout_ms = timeout_ms
        self.max_response_bytes = max_response_bytes

    def execute(self, collection_name: str, pipeline: list[dict[str, object]]) -> QueryResult:
        started = perf_counter()
        try:
            cursor = self.database[collection_name].aggregate(
                pipeline,
                allowDiskUse=False,
                maxTimeMS=self.timeout_ms,
            )
            rows = self._normalize_rows(list(cursor))
        except PyMongoError as error:
            raise MongoQueryExecutionError(
                "The validated aggregation could not be executed."
            ) from error
        elapsed_ms = round((perf_counter() - started) * 1000)
        columns = tuple(dict.fromkeys(key for row in rows for key in row))
        return QueryResult(columns=columns, rows=rows, execution_time_ms=elapsed_ms)

    def _normalize_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        response_size = 0
        for row in rows:
            item = {str(key): self._cell(value) for key, value in row.items()}
            response_size += len(
                json.dumps(item, separators=(",", ":"), ensure_ascii=False).encode()
            )
            if response_size > self.max_response_bytes:
                raise QueryResultTooLargeError(
                    "The query result exceeds the configured response limit."
                )
            normalized.append(item)
        return normalized

    def _cell(self, value: object) -> object:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, (ObjectId, UUID, Decimal, Decimal128)):
            return str(value)
        return json.dumps(self._json_value(value), separators=(",", ":"), ensure_ascii=False)

    def _json_value(self, value: object) -> object:
        if isinstance(value, dict):
            return {str(key): self._json_value(child) for key, child in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_value(item) for item in value]
        return self._cell(value)
