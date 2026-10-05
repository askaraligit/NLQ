"""Focused unit coverage for the Phase 4 NLQ trust boundary."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.llm_service import GeneratedQuery, OpenAIProvider, VisualizationProposal
from app.services.nlq_service import NLQService
from app.services.schema_service import SchemaService
from app.services.sql_service import QueryResult, SQLPolicyError, SQLValidator

pytestmark = pytest.mark.anyio


def test_schema_service_selects_related_sales_context() -> None:
    context = SchemaService(max_tables=6).context_for("Show monthly sales revenue by customer")

    assert "sales_orders" in context.table_names
    assert "customers" in context.table_names
    assert context.relationships
    assert "total_amount" in context.column_names("sales_orders")


def test_sql_validator_accepts_a_curated_sales_aggregate() -> None:
    context = SchemaService(max_tables=6).context_for("Show monthly sales revenue")

    normalized = SQLValidator().validate(
        "SELECT DATE_TRUNC('month', so.order_date) AS month, "
        "SUM(so.total_amount) AS revenue FROM erp.sales_orders AS so "
        "GROUP BY DATE_TRUNC('month', so.order_date)",
        context,
    )

    assert "erp.sales_orders AS so" in normalized


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM erp.sales_orders",
        "SELECT * FROM erp.sales_orders",
        "SELECT pg_sleep(1) FROM erp.sales_orders",
        "SELECT so.total_amount FROM app.tenants AS so",
        "SELECT so.tenant_id FROM erp.sales_orders AS so",
        "WITH changed AS (DELETE FROM erp.sales_orders RETURNING id) SELECT * FROM changed",
        "SELECT so.total_amount FROM erp.sales_orders AS so; DELETE FROM erp.sales_orders",
    ],
)
def test_sql_validator_rejects_unsafe_or_unapproved_sql(sql: str) -> None:
    context = SchemaService(max_tables=6).context_for("Show monthly sales revenue")

    with pytest.raises(SQLPolicyError):
        SQLValidator().validate(sql, context)


async def test_openai_provider_requests_strict_structured_output() -> None:
    captured: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "sql": "SELECT so.total_amount FROM erp.sales_orders AS so",
                                        "explanation": "Lists sales order totals.",
                                        "visualization": {
                                            "chart_type": "table",
                                            "x_axis": "",
                                            "y_axis": "",
                                        },
                                    }
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
        timeout_seconds=5,
        max_output_tokens=500,
        transport=httpx.MockTransport(responder),
    )
    proposal = await provider.generate_query(
        "Show sales totals", SchemaService(max_tables=6).context_for("Show sales totals")
    )

    assert proposal.visualization.chart_type == "table"
    assert captured["text"]["format"]["strict"] is True
    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["text"]["format"]["schema"]["$defs"]["VisualizationProposal"]["required"] == [
        "chart_type",
        "x_axis",
        "y_axis",
    ]


async def test_nlq_endpoint_reports_unavailable_without_runtime_configuration() -> None:
    application = create_app(Settings(_env_file=None))
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/nlq/query", json={"question": "Show sales"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Database runtime is not configured."


async def test_nlq_endpoint_requires_an_authenticated_user() -> None:
    application = create_app(Settings(_env_file=None))
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/nlq/query",
                json={"question": "Show sales", "conversationId": None},
            )

    assert response.status_code == 503
    assert response.json()["detail"] == "Database runtime is not configured."


def test_visualization_metadata_requires_result_columns() -> None:
    proposal = GeneratedQuery(
        sql="SELECT 1",
        explanation="Shows revenue by month.",
        visualization=VisualizationProposal(chart_type="bar", x_axis="month", y_axis="revenue"),
    )
    result = QueryResult(
        columns=("month", "revenue"),
        rows=[{"month": "2026-01", "revenue": "1200.00"}],
        execution_time_ms=5,
    )

    assert NLQService._visualization(proposal, result) == ("bar", "month", "revenue")


def test_visualization_metadata_falls_back_to_table_for_invalid_axes() -> None:
    proposal = GeneratedQuery(
        sql="SELECT 1",
        explanation="Shows revenue.",
        visualization=VisualizationProposal(chart_type="line", x_axis="missing", y_axis="revenue"),
    )
    result = QueryResult(columns=("month", "revenue"), rows=[], execution_time_ms=5)

    assert NLQService._visualization(proposal, result) == ("table", None, None)
