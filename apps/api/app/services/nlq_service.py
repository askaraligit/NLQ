"""NLQ orchestration with no execution path around SQL validation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID, uuid4

from app.services.llm_service import GeneratedQuery, LLMProvider
from app.services.schema_service import SchemaService
from app.services.sql_service import QueryExecutor, QueryResult, SQLValidator
from app.services.workspace_service import ConversationContextTurn


@dataclass(frozen=True)
class QueryResponseData:
    query_id: UUID
    sql: str
    columns: tuple[str, ...]
    rows: list[dict[str, object]]
    summary: str
    visualization_type: str
    x_axis: str | None
    y_axis: str | None
    execution_time_ms: int


class NLQService:
    def __init__(
        self,
        schema_service: SchemaService,
        provider: LLMProvider,
        validator: SQLValidator,
        executor: QueryExecutor,
    ) -> None:
        self.schema_service = schema_service
        self.provider = provider
        self.validator = validator
        self.executor = executor

    async def query(
        self, question: str, conversation: tuple[ConversationContextTurn, ...] = ()
    ) -> QueryResponseData:
        started = perf_counter()
        context = self.schema_service.context_for(question)
        proposal = await self.provider.generate_query(question, context, conversation)
        sql = self.validator.validate(proposal.sql, context)
        result = await asyncio.to_thread(self.executor.execute, sql)
        visualization_type, x_axis, y_axis = self._visualization(proposal, result)
        elapsed_ms = round((perf_counter() - started) * 1000)
        return QueryResponseData(
            query_id=uuid4(),
            sql=sql,
            columns=result.columns,
            rows=result.rows,
            summary=self._summary(proposal, result),
            visualization_type=visualization_type,
            x_axis=x_axis,
            y_axis=y_axis,
            execution_time_ms=max(elapsed_ms, result.execution_time_ms),
        )

    @staticmethod
    def _summary(proposal: GeneratedQuery, result: QueryResult) -> str:
        if not result.rows:
            return "No records matched this question."
        row_word = "row" if len(result.rows) == 1 else "rows"
        return f"Returned {len(result.rows)} {row_word}. {proposal.explanation.strip()}"

    @staticmethod
    def _visualization(
        proposal: GeneratedQuery, result: QueryResult
    ) -> tuple[str, str | None, str | None]:
        columns = set(result.columns)
        visualization = proposal.visualization
        if visualization.chart_type == "table":
            return "table", None, None
        if visualization.x_axis in columns and visualization.y_axis in columns:
            return visualization.chart_type, visualization.x_axis, visualization.y_axis
        return "table", None, None
