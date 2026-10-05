"""Focused unit coverage for the Phase 4 NLQ trust boundary."""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.llm_service import OpenAIProvider
from app.services.nlq_service import QueryResponseData
from app.services.schema_service import SchemaService
from app.services.sql_service import SQLPolicyError, SQLValidator

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
    assert response.json()["error"]["code"] == "NLQ_UNAVAILABLE"


async def test_nlq_endpoint_serializes_a_safe_service_result() -> None:
    class StubService:
        async def query(self, question: str) -> QueryResponseData:
            assert question == "Show sales"
            return QueryResponseData(
                query_id=UUID("00000000-0000-0000-0000-000000000001"),
                sql="SELECT so.total_amount FROM erp.sales_orders AS so",
                columns=("total_amount",),
                rows=[{"total_amount": "1250.00"}],
                summary="Returned 1 row. Lists sales totals.",
                visualization_type="table",
                x_axis=None,
                y_axis=None,
                execution_time_ms=12,
            )

    application = create_app(Settings(_env_file=None))
    async with application.router.lifespan_context(application):
        application.state.nlq_service = StubService()
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/nlq/query",
                json={"question": "Show sales", "conversationId": None},
            )

    assert response.status_code == 200
    assert response.json() == {
        "queryId": "00000000-0000-0000-0000-000000000001",
        "question": "Show sales",
        "sql": "SELECT so.total_amount FROM erp.sales_orders AS so",
        "columns": [{"name": "total_amount"}],
        "rows": [{"total_amount": "1250.00"}],
        "summary": "Returned 1 row. Lists sales totals.",
        "visualization": {"type": "table", "xAxis": None, "yAxis": None},
        "executionTimeMs": 12,
    }
