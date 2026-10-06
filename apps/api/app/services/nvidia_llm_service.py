"""NVIDIA NIM chat-completions adapter."""

from __future__ import annotations

import json
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from app.services.llm_service import (
    GeneratedMongoQuery,
    GeneratedQuery,
    LLMProvider,
    ProviderResponseError,
)
from app.services.schema_service import SchemaContext
from app.services.workspace_service import ConversationContextTurn


class NvidiaProvider(LLMProvider):
    """Generate typed NLQ proposals through NVIDIA's OpenAI-compatible endpoint."""

    endpoint = "https://integrate.api.nvidia.com/v1/chat/completions"

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
        result = await self._generate(
            question,
            context,
            conversation,
            (
                "You generate safe analytics SQL for the approved PostgreSQL schema.",
                "Return one JSON object with sql, explanation, and visualization.",
                "Generate exactly one SELECT or UNION query using only approved tables and columns.",
                "Never mutate data, use CTEs, comments, locking clauses, or system catalogs.",
            ),
            GeneratedQuery,
        )
        assert isinstance(result, GeneratedQuery)
        return result

    async def generate_mongo_query(
        self,
        question: str,
        context: SchemaContext,
        conversation: Sequence[ConversationContextTurn] = (),
    ) -> GeneratedMongoQuery:
        result = await self._generate(
            question,
            context,
            conversation,
            (
                "You generate safe MongoDB aggregation pipelines for the approved database.",
                "Return one JSON object with collection, pipeline, explanation, and visualization.",
                "Use only $match, $project, $group, $sort, $limit, $unwind, or $count stages.",
                "Do not use $lookup, $out, $merge, $where, JavaScript, or write operations.",
            ),
            GeneratedMongoQuery,
        )
        assert isinstance(result, GeneratedMongoQuery)
        return result

    async def _generate(
        self,
        question: str,
        context: SchemaContext,
        conversation: Sequence[ConversationContextTurn],
        instructions: tuple[str, ...],
        response_model: type[GeneratedQuery] | type[GeneratedMongoQuery],
    ) -> GeneratedQuery | GeneratedMongoQuery:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "\n".join((*instructions, "Do not use Markdown."))},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "schema_context": context.as_prompt_data(),
                            "prior_turns": [
                                {"question": turn.question, "summary": turn.summary}
                                for turn in conversation
                            ],
                        }
                    ),
                },
            ],
            "max_tokens": self.max_output_tokens,
            "temperature": 0,
            "stream": False,
            # Nemotron reasoning is useful for interactive chat, but NLQ requires a small,
            # machine-readable proposal within the request timeout.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as error:
            raise ProviderResponseError("The language-model request timed out.") from error
        except httpx.HTTPError as error:
            raise ProviderResponseError("The language-model service is unavailable.") from error
        if response.status_code >= 400:
            raise ProviderResponseError("The language-model service rejected the request.")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Message content was not text.")
            return response_model.model_validate_json(self._json_content(content))
        except (KeyError, IndexError, TypeError, ValidationError, json.JSONDecodeError) as error:
            raise ProviderResponseError(
                "The language-model response did not match the required schema."
            ) from error

    @staticmethod
    def _json_content(content: str) -> str:
        candidate = content.strip()
        if candidate.startswith("```"):
            candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
            candidate = candidate.rsplit("```", 1)[0].strip()
        return candidate
