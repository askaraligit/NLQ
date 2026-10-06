"""Typed provider boundary for structured NLQ generation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings
from app.services.schema_service import SchemaContext
from app.services.workspace_service import ConversationContextTurn


class VisualizationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_type: Literal["table", "bar", "line", "area", "pie"]
    x_axis: str = Field(description="Result column for the horizontal axis, or an empty string.")
    y_axis: str = Field(description="Result column for the vertical axis, or an empty string.")


class GeneratedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str = Field(description="One PostgreSQL SELECT statement.")
    explanation: str = Field(description="Brief description of what the query measures.")
    visualization: VisualizationProposal


class MongoVisualizationProposal(BaseModel):
    """Chart hints may include provider-specific display metadata that the API does not use."""

    model_config = ConfigDict(extra="ignore")

    chart_type: Literal["table", "bar", "line", "area", "pie"]
    x_axis: str = ""
    y_axis: str = ""


class GeneratedMongoQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    collection: str
    pipeline: list[dict[str, object]] = Field(min_length=1, max_length=12)
    explanation: str
    visualization: MongoVisualizationProposal


class ProviderConfigurationError(RuntimeError):
    """Provider configuration cannot safely produce an NLQ response."""


class ProviderResponseError(RuntimeError):
    """A provider declined, timed out, or returned an unusable response."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate_query(
        self,
        question: str,
        context: SchemaContext,
        conversation: Sequence[ConversationContextTurn] = (),
    ) -> GeneratedQuery:
        """Generate structured SQL proposal from the curated schema context."""

    @abstractmethod
    async def generate_mongo_query(
        self,
        question: str,
        context: SchemaContext,
        conversation: Sequence[ConversationContextTurn] = (),
    ) -> GeneratedMongoQuery:
        """Generate a read-only MongoDB aggregation proposal."""


class OpenAIProvider(LLMProvider):
    """OpenAI Responses API adapter using strict JSON-schema structured output."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int,
        max_output_tokens: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.transport = transport

    async def generate_query(
        self,
        question: str,
        context: SchemaContext,
        conversation: Sequence[ConversationContextTurn] = (),
    ) -> GeneratedQuery:
        return await self._generate(
            question,
            context,
            conversation,
            instructions=(
                "You generate safe analytics SQL for the approved PostgreSQL schema.",
                "Return only the requested JSON object.",
                "Generate exactly one SELECT or UNION query.",
                "Use only schema tables and columns in the provided context.",
                "Fully qualify tables and use explicit columns; never use SELECT *.",
                "Never mutate data or use CTEs, comments, locking clauses, or system catalogs.",
                "Use only normal aggregate functions and never filter or infer a tenant.",
                "Explain the query definition, not unobserved results.",
            ),
            response_name="nlq_query",
            response_model=GeneratedQuery,
            strict_response_schema=True,
        )

    async def generate_mongo_query(
        self,
        question: str,
        context: SchemaContext,
        conversation: Sequence[ConversationContextTurn] = (),
    ) -> GeneratedMongoQuery:
        return await self._generate(
            question,
            context,
            conversation,
            instructions=(
                "You generate safe MongoDB aggregation pipelines for the approved database.",
                "Return only the requested JSON object.",
                "Use exactly one approved collection and its listed fields.",
                "Use only $match, $project, $group, $sort, $limit, $unwind, or $count stages.",
                "Do not use $lookup, $out, $merge, $where, JavaScript, or any write operation.",
                "Do not infer data that is not present in the result.",
            ),
            response_name="nlq_mongodb_pipeline",
            response_model=GeneratedMongoQuery,
            strict_response_schema=False,
        )

    async def _generate(
        self,
        question: str,
        context: SchemaContext,
        conversation: Sequence[ConversationContextTurn],
        *,
        instructions: tuple[str, ...],
        response_name: str,
        response_model: type[GeneratedQuery] | type[GeneratedMongoQuery],
        strict_response_schema: bool,
    ) -> GeneratedQuery | GeneratedMongoQuery:
        payload = {
            "model": self.model,
            "instructions": "\n".join(instructions),
            "input": json.dumps(
                {
                    "question": question,
                    "schema_context": context.as_prompt_data(),
                    "prior_turns": [
                        {"question": turn.question, "summary": turn.summary}
                        for turn in conversation
                    ],
                }
            ),
            "max_output_tokens": self.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": response_name,
                    # MongoDB stages have arbitrary field names. OpenAI's strict schema mode
                    # cannot represent that dynamic object shape; server-side validation remains
                    # mandatory before any aggregation can execute.
                    "strict": strict_response_schema,
                    "schema": response_model.model_json_schema(),
                }
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as error:
            raise ProviderResponseError("The language-model request timed out.") from error
        except httpx.HTTPError as error:
            raise ProviderResponseError("The language-model service is unavailable.") from error
        if response.status_code >= 400:
            raise ProviderResponseError("The language-model service rejected the request.")
        return self._parse_response(response.json(), response_model)

    @staticmethod
    def _parse_response(
        payload: object,
        response_model: type[GeneratedQuery] | type[GeneratedMongoQuery] = GeneratedQuery,
    ) -> GeneratedQuery | GeneratedMongoQuery:
        if not isinstance(payload, dict) or payload.get("status") == "incomplete":
            raise ProviderResponseError("The language-model response was incomplete.")
        output_text = payload.get("output_text")
        if not isinstance(output_text, str):
            output_text = ""
            for item in payload.get("output", []):
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for content in item.get("content", []):
                    if isinstance(content, dict) and content.get("type") == "output_text":
                        output_text = content.get("text", "")
                        break
        if not output_text:
            raise ProviderResponseError(
                "The language-model response contained no structured output."
            )
        try:
            return response_model.model_validate_json(output_text)
        except ValidationError as error:
            raise ProviderResponseError(
                "The language-model response did not match the required schema."
            ) from error


def create_llm_provider(settings: Settings) -> LLMProvider:
    if not settings.llm_model:
        raise ProviderConfigurationError("LLM_MODEL is required to run NLQ queries.")
    if settings.llm_provider == "openai":
        if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value().strip():
            raise ProviderConfigurationError("LLM_API_KEY is required to run NLQ queries.")
        return OpenAIProvider(
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    if settings.llm_provider == "nvidia":
        if settings.nvidia_api_key is None or not settings.nvidia_api_key.get_secret_value().strip():
            raise ProviderConfigurationError("NVIDIA_API_KEY is required to run NLQ queries.")
        from app.services.nvidia_llm_service import NvidiaProvider

        return NvidiaProvider(
            api_key=settings.nvidia_api_key.get_secret_value(),
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    raise ProviderConfigurationError(f"LLM provider '{settings.llm_provider}' is not implemented.")
