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
        payload = {
            "model": self.model,
            "instructions": "\n".join(
                (
                    "You generate safe analytics SQL for a PostgreSQL ERP database.",
                    "Return only the requested JSON object.",
                    "Generate exactly one SELECT or UNION query.",
                    "Use only erp-schema tables and columns in the provided context.",
                    "Fully qualify tables and use explicit columns; never use SELECT *.",
                    "Never mutate data or use CTEs, comments, locking clauses, or system catalogs.",
                    "Use only normal aggregate functions and never filter or infer a tenant.",
                    "Explain the query definition, not unobserved results.",
                )
            ),
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
                    "name": "nlq_query",
                    "strict": True,
                    "schema": GeneratedQuery.model_json_schema(),
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
        return self._parse_response(response.json())

    @staticmethod
    def _parse_response(payload: object) -> GeneratedQuery:
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
            return GeneratedQuery.model_validate_json(output_text)
        except ValidationError as error:
            raise ProviderResponseError(
                "The language-model response did not match the required schema."
            ) from error


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider != "openai":
        raise ProviderConfigurationError(
            f"LLM provider '{settings.llm_provider}' is not implemented in Phase 4."
        )
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value().strip():
        raise ProviderConfigurationError("LLM_API_KEY is required to run NLQ queries.")
    if not settings.llm_model:
        raise ProviderConfigurationError("LLM_MODEL is required to run NLQ queries.")
    return OpenAIProvider(
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
    )
