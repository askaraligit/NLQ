"""Pure synthetic ERP fixture generation, independent of PostgreSQL and wall-clock time."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from random import Random
from uuid import UUID, uuid5

SEED_VERSION = "erp-demo-v1"
AS_OF = date(2026, 9, 30)
START_DATE = date(2025, 1, 1)
NAMESPACE = UUID("25de0a9c-2ed0-41c4-bdc4-9800a88f206b")
PRIMARY_TENANT_ID = uuid5(NAMESPACE, "tenant:deccan-demo")
SECONDARY_TENANT_ID = uuid5(NAMESPACE, "tenant:konkan-demo")
ZERO = Decimal("0.00")
CENT = Decimal("0.01")

Row = dict[str, object]


@dataclass(frozen=True)
class TenantSpec:
    slug: str
    name: str
    customers: int
    suppliers: int
    categories: int
    products: int
    purchase_orders: int
    sales_orders: int
    random_seed: int


@dataclass
class SeedDataset:
    tenant: Row
    tables: dict[str, list[Row]]


SPECS = (
    TenantSpec(
        "deccan-demo", "Deccan Industrial Supplies (Synthetic)", 60, 20, 8, 80, 300, 600, 260930
    ),
    TenantSpec("konkan-demo", "Konkan Office Solutions (Synthetic)", 8, 4, 4, 12, 24, 48, 260931),
)

# Prices are deterministic whole-rupee inputs, then handled exclusively as Decimal.
CATALOG = (
    ("Power Tools", "Cordless Drill", "unit", 3200, 18),
    ("Safety Equipment", "Safety Helmet", "unit", 340, 18),
    ("Electrical Supplies", "Industrial Cable 100m", "roll", 6400, 18),
    ("Plumbing Supplies", "Brass Valve", "unit", 1250, 18),
    ("Office Equipment", "Document Scanner", "unit", 9200, 18),
    ("Packaging", "Corrugated Box Pack", "pack", 480, 12),
    ("Fasteners", "Steel Bolt Pack", "pack", 650, 18),
    ("Material Handling", "Platform Trolley", "unit", 5800, 18),
)
LOCATIONS = (
    ("Pune", "Maharashtra"),
    ("Mumbai", "Maharashtra"),
    ("Bengaluru", "Karnataka"),
    ("Chennai", "Tamil Nadu"),
    ("Hyderabad", "Telangana"),
    ("Ahmedabad", "Gujarat"),
    ("Jaipur", "Rajasthan"),
    ("Kochi", "Kerala"),
)
BUSINESSES = (
    "Machine Works",
    "Engineering",
    "Fabricators",
    "Components",
    "Trading",
    "Packaging",
    "Manufacturing",
    "Projects",
    "Facilities",
    "Retail",
)
TABLE_ORDER = (
    "product_categories",
    "customers",
    "suppliers",
    "products",
    "purchase_orders",
    "purchase_order_items",
    "sales_orders",
    "sales_order_items",
    "purchase_invoices",
    "sales_invoices",
    "payments",
    "stock",
)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_amounts(item: Row) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = money(item["quantity"] * item["unit_price"])
    tax = money(item["quantity"] * item["unit_price"] * item["tax_rate"] / Decimal(100))
    return subtotal, tax, subtotal + tax


def _timestamp(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), UTC).replace(hour=9)


def _id(slug: str, kind: str, key: object) -> UUID:
    return uuid5(NAMESPACE, f"{slug}:{kind}:{key}")


def _row(spec: TenantSpec, kind: str, key: object, day: date = START_DATE) -> Row:
    return {
        "id": _id(spec.slug, kind, key),
        "tenant_id": uuid5(NAMESPACE, f"tenant:{spec.slug}"),
        "created_at": _timestamp(day),
        "updated_at": _timestamp(day),
    }


def _parties(spec: TenantSpec, kind: str, count: int) -> list[Row]:
    rows = []
    for index in range(count):
        city, state = LOCATIONS[index % len(LOCATIONS)]
        rows.append(
            {
                **_row(spec, kind, index),
                "code": f"{'CUS' if kind == 'customer' else 'SUP'}-{index + 1:03}",
                "name": f"Demo {city} {BUSINESSES[index % len(BUSINESSES)]} {index + 1:02}",
                "email": f"{kind}{index + 1}@{spec.slug}.example.invalid",
                # No realistic phone numbers: all contact data must remain synthetic.
                "phone": None,
                "city": city,
                "state": state,
                "country": "India",
                "is_active": index != count - 1,
            }
        )
    return rows


def _catalog(spec: TenantSpec, tables: dict[str, list[Row]]) -> None:
    for index in range(spec.categories):
        category, _, _, _, _ = CATALOG[index]
        tables["product_categories"].append(
            {
                **_row(spec, "category", index),
                "name": category,
                "description": f"Synthetic {category.lower()} merchandise for analytics exercises.",
            }
        )
    for index in range(spec.products):
        category_index = index % spec.categories
        _, name, unit, base_price, _ = CATALOG[category_index]
        variation = index // spec.categories + 1
        cost = money(Decimal(base_price) * (Decimal(100) + Decimal(variation * 7)) / Decimal(100))
        tables["products"].append(
            {
                **_row(spec, "product", index),
                "sku": f"SKU-{index + 1:04}",
                "name": f"{name} Series {variation:02}",
                "description": "Synthetic catalog product; no actual brand or customer data.",
                "category_id": _id(spec.slug, "category", category_index),
                "unit": unit,
                "cost_price": cost,
                "selling_price": money(cost * Decimal("1.28")),
                "reorder_level": Decimal(20 + index % 6 * 10).quantize(CENT),
                "is_active": True,
            }
        )


def _order_date(index: int, count: int) -> date:
    # Span every month, leaving time for the final invoices and settlements.
    last_day = AS_OF - timedelta(days=12)
    return START_DATE + timedelta(days=index * (last_day - START_DATE).days // (count - 1))


def _orders(spec: TenantSpec, tables: dict[str, list[Row]], rng: Random, kind: str) -> None:
    purchase = kind == "purchase"
    count = spec.purchase_orders if purchase else spec.sales_orders
    parties = tables["suppliers" if purchase else "customers"]
    prefix = "PO" if purchase else "SO"
    for index in range(count):
        day = _order_date(index, count)
        # First customers are deliberately dormant; the last customer never orders.
        eligible = len(parties) - 1
        dormant = max(1, len(parties) // 6)
        if not purchase and day > AS_OF - timedelta(days=120):
            party_index = dormant + index % (eligible - dormant)
        else:
            party_index = index % eligible
        status = "received" if purchase else "delivered"
        if index % 17 == 0:
            status = "cancelled"
        elif index % 7 == 0:
            status = "confirmed"
        elif index % 19 == 0:
            status = "draft"
        elif not purchase and index % 11 == 0:
            status = "shipped"
        items = []
        for position, product_index in enumerate(
            rng.sample(range(spec.products), rng.randint(2, 5))
        ):
            product = tables["products"][product_index]
            quantity = Decimal(rng.randint(12, 85) if purchase else rng.randint(2, 24)).quantize(
                CENT
            )
            unit_price = product["cost_price" if purchase else "selling_price"]
            # Historical price variation creates useful comparisons without float arithmetic.
            unit_price = money(unit_price * (Decimal("0.95") if day.year == 2025 else Decimal(1)))
            item = {
                **_row(spec, f"{kind}_item", f"{index}:{position}", day),
                "order_id": _id(spec.slug, f"{kind}_order", index),
                "product_id": product["id"],
                "quantity": quantity,
                "unit_price": unit_price,
                "tax_rate": Decimal(CATALOG[product_index % spec.categories][4]).quantize(CENT),
            }
            items.append(item)
        amounts = [line_amounts(item) for item in items]
        subtotal = sum((amount[0] for amount in amounts), ZERO)
        tax = sum((amount[1] for amount in amounts), ZERO)
        order = {
            **_row(spec, f"{kind}_order", index, day),
            "order_number": f"{prefix}-{day.year}-{index + 1:05}",
            "supplier_id" if purchase else "customer_id": parties[party_index]["id"],
            "order_date": day,
            "expected_date" if purchase else "delivery_date": day + timedelta(days=7),
            "status": status,
            "currency": "INR",
            "subtotal": subtotal,
            "tax_amount": tax,
            "total_amount": subtotal + tax,
        }
        tables[f"{kind}_orders"].append(order)
        tables[f"{kind}_order_items"].extend(items)
        if status in {"received", "delivered", "shipped"}:
            _invoice(spec, tables, kind, index, order)


def _invoice(
    spec: TenantSpec, tables: dict[str, list[Row]], kind: str, index: int, order: Row
) -> None:
    day = order["order_date"] + timedelta(days=7)
    due_day = day + timedelta(days=30)
    mode = index % 5
    # Current balances as of AS_OF; no receipts are generated after the fixture cutoff.
    status = "paid" if mode in {0, 1, 2} else "partially_paid" if mode == 3 else "issued"
    if mode == 4 and due_day < AS_OF:
        status = "overdue"
    invoice_id = _id(spec.slug, f"{kind}_invoice", index)
    invoice = {
        **_row(spec, f"{kind}_invoice", index, day),
        "invoice_number": f"{'PI' if kind == 'purchase' else 'SI'}-{day.year}-{index + 1:05}",
        "order_id": order["id"],
        "invoice_date": day,
        "due_date": due_day,
        "status": status,
        "currency": "INR",
        "subtotal": order["subtotal"],
        "tax_amount": order["tax_amount"],
        "total_amount": order["total_amount"],
    }
    tables[f"{kind}_invoices"].append(invoice)
    if mode == 4:
        return
    total = invoice["total_amount"]
    if mode == 2:
        first = money(total * Decimal("0.40"))
        amounts = (first, total - first)
    else:
        amounts = (money(total * Decimal("0.35")) if mode == 3 else total,)
    for position, amount in enumerate(amounts):
        payment_day = min(day + timedelta(days=3 + position * 14), AS_OF)
        payment_prefix = "OUT" if kind == "purchase" else "IN"
        tables["payments"].append(
            {
                **_row(spec, f"{kind}_payment", f"{index}:{position}", payment_day),
                "payment_number": f"{payment_prefix}-{index + 1:05}-{position + 1}",
                "purchase_invoice_id": invoice_id if kind == "purchase" else None,
                "sales_invoice_id": invoice_id if kind == "sales" else None,
                "payment_date": payment_day,
                "amount": amount,
                "method": ("bank_transfer", "upi", "cheque", "card")[index % 4],
                "reference": f"SYNTHETIC-{kind.upper()}-{index + 1:05}-{position + 1}",
            }
        )
    invoice["updated_at"] = _timestamp(payment_day)


def _stock(spec: TenantSpec, tables: dict[str, list[Row]], rng: Random) -> None:
    # A point-in-time snapshot, not a stock ledger reconstructed from these sample orders.
    for index, product in enumerate(tables["products"]):
        for warehouse in ("Pune Central", "Bengaluru South"):
            level = int(product["reorder_level"])
            quantity = (
                rng.randint(0, max(1, level // 4)) if index % 7 == 0 else rng.randint(50, 320)
            )
            reserved = min(quantity, rng.randint(0, 12))
            tables["stock"].append(
                {
                    **_row(spec, "stock", f"{index}:{warehouse}", AS_OF),
                    "product_id": product["id"],
                    "warehouse": warehouse,
                    "quantity": Decimal(quantity).quantize(CENT),
                    "reserved_quantity": Decimal(reserved).quantize(CENT),
                }
            )


def generate_datasets() -> list[SeedDataset]:
    """Return independent, reproducible fixtures for both demonstration tenants."""
    datasets = []
    for spec in SPECS:
        tables = {table: [] for table in TABLE_ORDER}
        tables["customers"] = _parties(spec, "customer", spec.customers)
        tables["suppliers"] = _parties(spec, "supplier", spec.suppliers)
        _catalog(spec, tables)
        rng = Random(spec.random_seed)
        _orders(spec, tables, rng, "purchase")
        _orders(spec, tables, rng, "sales")
        _stock(spec, tables, rng)
        dataset = SeedDataset(
            tenant={
                "id": uuid5(NAMESPACE, f"tenant:{spec.slug}"),
                "name": spec.name,
                "slug": spec.slug,
                "created_at": _timestamp(START_DATE),
                "updated_at": _timestamp(START_DATE),
            },
            tables=tables,
        )
        validate_dataset(dataset)
        datasets.append(dataset)
    return datasets


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_dataset(dataset: SeedDataset) -> None:
    """Check money, tenant ownership, references and chronology before writing anything."""
    tenant_id = dataset.tenant["id"]
    tables = dataset.tables
    for table, rows in tables.items():
        _require(len({row["id"] for row in rows}) == len(rows), f"Duplicate IDs in {table}")
        for row in rows:
            _require(row["tenant_id"] == tenant_id, f"Cross-tenant row in {table}")
            _require(row["created_at"] <= row["updated_at"], f"Invalid timestamps in {table}")
            _require(row["updated_at"].date() <= AS_OF, f"Future timestamp in {table}")
    categories = {row["id"] for row in tables["product_categories"]}
    products = {row["id"]: row for row in tables["products"]}
    for product in products.values():
        _require(product["category_id"] in categories, "Unknown product category")
        _require(product["cost_price"] >= ZERO, "Negative product cost")
        _require(product["selling_price"] >= ZERO, "Negative product selling price")
    for stock in tables["stock"]:
        _require(stock["product_id"] in products, "Unknown stock product")
        _require(
            ZERO <= stock["reserved_quantity"] <= stock["quantity"], "Invalid stock quantities"
        )
    invoices = {}
    for kind, parties, party_key in (
        ("purchase", "suppliers", "supplier_id"),
        ("sales", "customers", "customer_id"),
    ):
        party_ids = {row["id"] for row in tables[parties]}
        orders = {row["id"]: row for row in tables[f"{kind}_orders"]}
        lines = defaultdict(list)
        for item in tables[f"{kind}_order_items"]:
            _require(item["order_id"] in orders, "Unknown line order")
            _require(item["product_id"] in products, "Unknown line product")
            _require(item["quantity"] > ZERO and item["unit_price"] >= ZERO, "Invalid line amount")
            lines[item["order_id"]].append(item)
        for order in orders.values():
            _require(order[party_key] in party_ids, "Unknown order party")
            _require(order["order_date"] <= AS_OF, "Future order")
            _require(len(lines[order["id"]]) >= 2, "Order needs multiple lines")
            amounts = [line_amounts(item) for item in lines[order["id"]]]
            for key, position in (("subtotal", 0), ("tax_amount", 1), ("total_amount", 2)):
                _require(
                    order[key] == sum((row[position] for row in amounts), ZERO), "Order mismatch"
                )
        for invoice in tables[f"{kind}_invoices"]:
            _require(invoice["order_id"] in orders, "Unknown invoice order")
            order = orders[invoice["order_id"]]
            _require(
                order["status"] not in {"cancelled", "draft", "confirmed"}, "Unfulfilled invoice"
            )
            _require(
                order["order_date"] <= invoice["invoice_date"] <= AS_OF, "Invalid invoice date"
            )
            _require(invoice["due_date"] >= invoice["invoice_date"], "Invalid invoice due date")
            for key in ("subtotal", "tax_amount", "total_amount"):
                _require(invoice[key] == order[key], "Invoice/order amount mismatch")
            invoices[(kind, invoice["id"])] = invoice
    paid = defaultdict(lambda: ZERO)
    for payment in tables["payments"]:
        purchase_id, sales_id = payment["purchase_invoice_id"], payment["sales_invoice_id"]
        _require((purchase_id is None) != (sales_id is None), "Payment must target one invoice")
        key = ("purchase", purchase_id) if purchase_id else ("sales", sales_id)
        _require(key in invoices, "Unknown payment invoice")
        _require(invoices[key]["invoice_date"] <= payment["payment_date"] <= AS_OF, "Payment date")
        _require(payment["amount"] > ZERO, "Payment must be positive")
        paid[key] += payment["amount"]
    for key, invoice in invoices.items():
        balance = invoice["total_amount"] - paid[key]
        _require(balance >= ZERO, "Overpayment")
        if invoice["status"] == "paid":
            _require(balance == ZERO, "Paid invoice has a balance")
        elif invoice["status"] == "partially_paid":
            _require(ZERO < paid[key] < invoice["total_amount"], "Partial invoice payment mismatch")
        else:
            _require(paid[key] == ZERO, "Unpaid invoice has payments")
            expected = "overdue" if invoice["due_date"] < AS_OF else "issued"
            _require(invoice["status"] == expected, "Incorrect unpaid invoice status")
