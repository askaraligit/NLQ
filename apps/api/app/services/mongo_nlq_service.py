"""MongoDB NLQ orchestration with aggregation-pipeline validation."""

from __future__ import annotations

import asyncio
import json
from time import perf_counter
from uuid import uuid4

from app.services.llm_service import GeneratedMongoQuery, LLMProvider
from app.services.mongo_service import MongoPipelineValidator, MongoQueryExecutor
from app.services.nlq_service import QueryResponseData
from app.services.schema_service import SchemaContext
from app.services.sql_service import QueryResult
from app.services.workspace_service import ConversationContextTurn


class MongoNLQService:
    def __init__(self, provider: LLMProvider, validator: MongoPipelineValidator) -> None:
        self.provider = provider
        self.validator = validator

    async def query_with_context(
        self,
        question: str,
        context: SchemaContext,
        executor: MongoQueryExecutor,
        conversation: tuple[ConversationContextTurn, ...] = (),
    ) -> QueryResponseData:
        started = perf_counter()
        proposal = await self.provider.generate_mongo_query(question, context, conversation)
        collection, pipeline = self.validator.validate(
            proposal.collection, proposal.pipeline, context
        )
        result = await asyncio.to_thread(executor.execute, collection, pipeline)
        visualization_type, x_axis, y_axis = self._visualization(proposal, result)
        elapsed_ms = round((perf_counter() - started) * 1000)
        return QueryResponseData(
            query_id=uuid4(),
            sql=json.dumps({"collection": collection, "pipeline": pipeline}, indent=2),
            query_language="mongodb",
            columns=result.columns,
            rows=result.rows,
            summary=self._summary(proposal, result),
            visualization_type=visualization_type,
            x_axis=x_axis,
            y_axis=y_axis,
            execution_time_ms=max(elapsed_ms, result.execution_time_ms),
        )

    @staticmethod
    def _summary(proposal: GeneratedMongoQuery, result: QueryResult) -> str:
        if not result.rows:
            return "No documents matched this question."
        return f"Returned {len(result.rows)} {'document' if len(result.rows) == 1 else 'documents'}. {proposal.explanation.strip()}"

    @staticmethod
    def _visualization(
        proposal: GeneratedMongoQuery, result: QueryResult
    ) -> tuple[str, str | None, str | None]:
        columns = set(result.columns)
        visualization = proposal.visualization
        if (
            visualization.chart_type != "table"
            and visualization.x_axis in columns
            and visualization.y_axis in columns
        ):
            return visualization.chart_type, visualization.x_axis, visualization.y_axis
        return "table", None, None
