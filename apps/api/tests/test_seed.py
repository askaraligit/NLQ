"""Check reproducibility and business usefulness without connecting to PostgreSQL."""

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from seeds.dataset import (
    AS_OF,
    PRIMARY_TENANT_ID,
    SECONDARY_TENANT_ID,
    SeedDataset,
    generate_datasets,
    validate_dataset,
)


@pytest.fixture(scope="module")
def datasets() -> list[SeedDataset]:
    return generate_datasets()


def test_seed_is_reproducible_with_disjoint_tenant_identifiers(datasets: list[SeedDataset]) -> None:
    assert datasets == generate_datasets()
    assert {dataset.tenant["id"] for dataset in datasets} == {
        PRIMARY_TENANT_ID,
        SECONDARY_TENANT_ID,
    }
    identifiers: set[UUID] = set()
    for dataset in datasets:
        validate_dataset(dataset)
        for rows in dataset.tables.values():
            for row in rows:
                assert isinstance(row["id"], UUID)
                assert row["id"] not in identifiers
                identifiers.add(row["id"])
                assert row["tenant_id"] == dataset.tenant["id"]
                assert row["created_at"] <= row["updated_at"]
                for value in row.values():
                    assert not isinstance(value, float), "Financial samples must use Decimal"
                    if isinstance(value, datetime):
                        assert value.tzinfo is not None
                        assert value.date() <= AS_OF
                    elif isinstance(value, date):
                        # Due dates and expected delivery dates may be after the snapshot.
                        assert value.year >= 2024


def test_seed_validation_rejects_tenant_mismatch(datasets: list[SeedDataset]) -> None:
    invalid = deepcopy(datasets[0])
    invalid.tables["customers"][0]["tenant_id"] = SECONDARY_TENANT_ID
    with pytest.raises(ValueError):
        validate_dataset(invalid)


def test_seed_validation_rejects_invalid_line_quantity(datasets: list[SeedDataset]) -> None:
    invalid = deepcopy(datasets[0])
    invalid.tables["sales_order_items"][0]["quantity"] = Decimal("-1")
    with pytest.raises(ValueError):
        validate_dataset(invalid)


def test_seed_answers_the_requested_analytics_examples(datasets: list[SeedDataset]) -> None:
    data = next(dataset for dataset in datasets if dataset.tenant["id"] == PRIMARY_TENANT_ID)
    tables = data.tables
    assert len(tables["customers"]) >= 50
    assert len(tables["products"]) >= 50
    assert len(tables["sales_orders"]) >= 500
    assert len(tables["purchase_orders"]) >= 250
    assert any(
        order["status"] == "confirmed" and order["total_amount"] > Decimal("100000")
        for order in tables["purchase_orders"]
    )
    completed_sales = [
        order for order in tables["sales_orders"] if order["status"] in {"shipped", "delivered"}
    ]
    months = {(order["order_date"].year, order["order_date"].month) for order in completed_sales}
    assert {(2026, month) for month in range(1, AS_OF.month + 1)} <= months
    assert any(year == 2025 for year, _ in months)
    recent_customers = {
        order["customer_id"]
        for order in completed_sales
        if order["order_date"] >= AS_OF - timedelta(days=90)
    }
    assert 0 < len(recent_customers) < len(tables["customers"])
    historical_customers = {order["customer_id"] for order in completed_sales}
    assert historical_customers - recent_customers, "Include dormant as well as new customers"
    assert {customer["id"] for customer in tables["customers"]} - historical_customers
    available_stock = defaultdict(lambda: Decimal("0"))
    for row in tables["stock"]:
        available_stock[row["product_id"]] += row["quantity"] - row["reserved_quantity"]
    below_reorder = [
        product
        for product in tables["products"]
        if available_stock[product["id"]] < product["reorder_level"]
    ]
    assert 0 < len(below_reorder) < len(tables["products"])
    for name in ("sales_invoices", "purchase_invoices"):
        assert {"paid", "partially_paid", "overdue", "issued"} <= {
            invoice["status"] for invoice in tables[name]
        }


def test_seed_validation_rejects_unbalanced_headers_and_payments(
    datasets: list[SeedDataset],
) -> None:
    invalid = deepcopy(datasets[0])
    invalid.tables["sales_orders"][0]["total_amount"] += Decimal("0.01")
    with pytest.raises(ValueError):
        validate_dataset(invalid)
    invalid = deepcopy(datasets[0])
    invalid.tables["payments"][0]["amount"] += Decimal("1000000000")
    with pytest.raises(ValueError):
        validate_dataset(invalid)
