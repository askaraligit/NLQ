"""Tenant-scoped ERP records with database-enforced relational integrity.

Cross-record relationships are read-only ORM navigation properties. Writes explicitly
provide tenant_id and referenced IDs; composite foreign keys enforce tenant identity.
Money is stored as exact decimals. Header totals are snapshots; item totals are generated.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantRecord

MONEY = Numeric(16, 2)
QUANTITY = Numeric(14, 2)
UNIT_PRICE = Numeric(14, 2)
TAX_RATE = Numeric(5, 2)


def tenant_identity() -> UniqueConstraint:
    return UniqueConstraint("tenant_id", "id")


def tenant_reference(column: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", column], [f"erp.{table}.tenant_id", f"erp.{table}.id"], ondelete="RESTRICT"
    )


def header_checks() -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint("subtotal >= 0 AND tax_amount >= 0", name="nonnegative_amounts"),
        CheckConstraint("total_amount = subtotal + tax_amount", name="total_amount"),
        CheckConstraint("currency = 'INR'", name="currency"),
    )


class PartyColumns:
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), server_default="India")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Customer(PartyColumns, TenantRecord):
    __tablename__ = "customers"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "code", name="uq_customers_tenant_code"),
        Index("ix_customers_tenant_name", "tenant_id", "name"),
        {"schema": "erp", "comment": "Customers placing sales orders."},
    )
    sales_orders: Mapped[list["SalesOrder"]] = relationship(
        back_populates="customer", viewonly=True
    )


class Supplier(PartyColumns, TenantRecord):
    __tablename__ = "suppliers"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "code", name="uq_suppliers_tenant_code"),
        Index("ix_suppliers_tenant_name", "tenant_id", "name"),
        {"schema": "erp", "comment": "Suppliers fulfilling purchase orders."},
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        back_populates="supplier", viewonly=True
    )


class ProductCategory(TenantRecord):
    __tablename__ = "product_categories"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "name", name="uq_product_categories_tenant_name"),
        {"schema": "erp", "comment": "Product categories used for inventory and sales grouping."},
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    products: Mapped[list["Product"]] = relationship(back_populates="category", viewonly=True)


class Product(TenantRecord):
    __tablename__ = "products"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
        tenant_reference("category_id", "product_categories"),
        CheckConstraint("cost_price >= 0 AND selling_price >= 0", name="nonnegative_prices"),
        CheckConstraint("reorder_level >= 0", name="nonnegative_reorder_level"),
        Index("ix_products_tenant_category", "tenant_id", "category_id"),
        Index("ix_products_tenant_name", "tenant_id", "name"),
        {"schema": "erp", "comment": "Catalog products; prices are denominated in INR."},
    )
    sku: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[UUID] = mapped_column()
    unit: Mapped[str] = mapped_column(String(20), server_default="unit")
    cost_price: Mapped[Decimal] = mapped_column(UNIT_PRICE)
    selling_price: Mapped[Decimal] = mapped_column(UNIT_PRICE)
    reorder_level: Mapped[Decimal] = mapped_column(QUANTITY, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    category: Mapped["ProductCategory"] = relationship(back_populates="products", viewonly=True)
    stock: Mapped[list["Stock"]] = relationship(back_populates="product", viewonly=True)


class HeaderAmounts:
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY)
    total_amount: Mapped[Decimal] = mapped_column(MONEY)


class PurchaseOrder(HeaderAmounts, TenantRecord):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "order_number", name="uq_purchase_orders_tenant_number"),
        tenant_reference("supplier_id", "suppliers"),
        *header_checks(),
        CheckConstraint("status IN ('draft', 'confirmed', 'received', 'cancelled')", name="status"),
        CheckConstraint("expected_date IS NULL OR expected_date >= order_date", name="dates"),
        Index("ix_purchase_orders_tenant_supplier", "tenant_id", "supplier_id"),
        Index("ix_purchase_orders_tenant_date", "tenant_id", "order_date"),
        Index("ix_purchase_orders_tenant_status", "tenant_id", "status"),
        {"schema": "erp", "comment": "Purchases from suppliers; confirmed orders await receipt."},
    )
    order_number: Mapped[str] = mapped_column(String(50))
    supplier_id: Mapped[UUID] = mapped_column()
    order_date: Mapped[date] = mapped_column(Date)
    expected_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), server_default="draft")
    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders", viewonly=True)
    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="order", viewonly=True)
    invoices: Mapped[list["PurchaseInvoice"]] = relationship(back_populates="order", viewonly=True)


class SalesOrder(HeaderAmounts, TenantRecord):
    __tablename__ = "sales_orders"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "order_number", name="uq_sales_orders_tenant_number"),
        tenant_reference("customer_id", "customers"),
        *header_checks(),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'shipped', 'delivered', 'cancelled')", name="status"
        ),
        CheckConstraint("delivery_date IS NULL OR delivery_date >= order_date", name="dates"),
        Index("ix_sales_orders_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_sales_orders_tenant_date", "tenant_id", "order_date"),
        Index("ix_sales_orders_tenant_status", "tenant_id", "status"),
        {"schema": "erp", "comment": "Customer sales orders and their monetary totals."},
    )
    order_number: Mapped[str] = mapped_column(String(50))
    customer_id: Mapped[UUID] = mapped_column()
    order_date: Mapped[date] = mapped_column(Date)
    delivery_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), server_default="draft")
    customer: Mapped["Customer"] = relationship(back_populates="sales_orders", viewonly=True)
    items: Mapped[list["SalesOrderItem"]] = relationship(back_populates="order", viewonly=True)
    invoices: Mapped[list["SalesInvoice"]] = relationship(back_populates="order", viewonly=True)


class ItemColumns:
    order_id: Mapped[UUID] = mapped_column()
    product_id: Mapped[UUID] = mapped_column()
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    unit_price: Mapped[Decimal] = mapped_column(UNIT_PRICE)
    tax_rate: Mapped[Decimal] = mapped_column(TAX_RATE, server_default="0")
    line_subtotal: Mapped[Decimal] = mapped_column(
        MONEY, Computed("round(quantity * unit_price, 2)", persisted=True)
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        MONEY, Computed("round(quantity * unit_price * tax_rate / 100::numeric, 2)", persisted=True)
    )
    line_total: Mapped[Decimal] = mapped_column(
        MONEY,
        Computed(
            "round(quantity * unit_price, 2) + "
            "round(quantity * unit_price * tax_rate / 100::numeric, 2)",
            persisted=True,
        ),
    )


def item_checks() -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("unit_price >= 0", name="nonnegative_price"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="tax_rate"),
    )


class PurchaseOrderItem(ItemColumns, TenantRecord):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        tenant_identity(),
        tenant_reference("order_id", "purchase_orders"),
        tenant_reference("product_id", "products"),
        *item_checks(),
        Index("ix_purchase_order_items_tenant_order", "tenant_id", "order_id"),
        Index("ix_purchase_order_items_tenant_product", "tenant_id", "product_id"),
        {
            "schema": "erp",
            "comment": "Purchase lines; monetary totals are generated by PostgreSQL.",
        },
    )
    order: Mapped["PurchaseOrder"] = relationship(back_populates="items", viewonly=True)
    product: Mapped["Product"] = relationship(viewonly=True)


class SalesOrderItem(ItemColumns, TenantRecord):
    __tablename__ = "sales_order_items"
    __table_args__ = (
        tenant_identity(),
        tenant_reference("order_id", "sales_orders"),
        tenant_reference("product_id", "products"),
        *item_checks(),
        Index("ix_sales_order_items_tenant_order", "tenant_id", "order_id"),
        Index("ix_sales_order_items_tenant_product", "tenant_id", "product_id"),
        {"schema": "erp", "comment": "Sales lines; monetary totals are generated by PostgreSQL."},
    )
    order: Mapped["SalesOrder"] = relationship(back_populates="items", viewonly=True)
    product: Mapped["Product"] = relationship(viewonly=True)


class InvoiceColumns(HeaderAmounts):
    invoice_number: Mapped[str] = mapped_column(String(50))
    order_id: Mapped[UUID] = mapped_column()
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), server_default="draft")


def invoice_checks() -> tuple[CheckConstraint, ...]:
    return (
        *header_checks(),
        CheckConstraint("due_date >= invoice_date", name="dates"),
        CheckConstraint(
            "status IN ('draft', 'issued', 'partially_paid', 'paid', 'overdue', 'cancelled')",
            name="status",
        ),
    )


class PurchaseInvoice(InvoiceColumns, TenantRecord):
    __tablename__ = "purchase_invoices"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "invoice_number", name="uq_purchase_invoices_tenant_number"),
        tenant_reference("order_id", "purchase_orders"),
        *invoice_checks(),
        Index("ix_purchase_invoices_tenant_order", "tenant_id", "order_id"),
        Index("ix_purchase_invoices_tenant_date", "tenant_id", "invoice_date"),
        Index("ix_purchase_invoices_tenant_due_status", "tenant_id", "due_date", "status"),
        {
            "schema": "erp",
            "comment": "Supplier invoices; supplier is derived through purchase order.",
        },
    )
    order: Mapped["PurchaseOrder"] = relationship(back_populates="invoices", viewonly=True)
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="purchase_invoice", viewonly=True
    )


class SalesInvoice(InvoiceColumns, TenantRecord):
    __tablename__ = "sales_invoices"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "invoice_number", name="uq_sales_invoices_tenant_number"),
        tenant_reference("order_id", "sales_orders"),
        *invoice_checks(),
        Index("ix_sales_invoices_tenant_order", "tenant_id", "order_id"),
        Index("ix_sales_invoices_tenant_date", "tenant_id", "invoice_date"),
        Index("ix_sales_invoices_tenant_due_status", "tenant_id", "due_date", "status"),
        {"schema": "erp", "comment": "Customer invoices; customer is derived through sales order."},
    )
    order: Mapped["SalesOrder"] = relationship(back_populates="invoices", viewonly=True)
    payments: Mapped[list["Payment"]] = relationship(back_populates="sales_invoice", viewonly=True)


class Payment(TenantRecord):
    __tablename__ = "payments"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "payment_number", name="uq_payments_tenant_number"),
        tenant_reference("purchase_invoice_id", "purchase_invoices"),
        tenant_reference("sales_invoice_id", "sales_invoices"),
        CheckConstraint(
            "(purchase_invoice_id IS NOT NULL) <> (sales_invoice_id IS NOT NULL)",
            name="exactly_one_invoice",
        ),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint(
            "method IN ('bank_transfer', 'cash', 'card', 'upi', 'cheque')", name="method"
        ),
        Index("ix_payments_tenant_purchase_invoice", "tenant_id", "purchase_invoice_id"),
        Index("ix_payments_tenant_sales_invoice", "tenant_id", "sales_invoice_id"),
        Index("ix_payments_tenant_date", "tenant_id", "payment_date"),
        {
            "schema": "erp",
            "comment": "Invoice payments: purchases are outgoing; sales are incoming, in INR.",
        },
    )
    payment_number: Mapped[str] = mapped_column(String(50))
    purchase_invoice_id: Mapped[UUID | None] = mapped_column()
    sales_invoice_id: Mapped[UUID | None] = mapped_column()
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    method: Mapped[str] = mapped_column(String(24))
    reference: Mapped[str | None] = mapped_column(String(200))
    purchase_invoice: Mapped["PurchaseInvoice | None"] = relationship(
        back_populates="payments", viewonly=True
    )
    sales_invoice: Mapped["SalesInvoice | None"] = relationship(
        back_populates="payments", viewonly=True
    )


class Stock(TenantRecord):
    __tablename__ = "stock"
    __table_args__ = (
        tenant_identity(),
        UniqueConstraint("tenant_id", "product_id", "warehouse", name="uq_stock_tenant_location"),
        tenant_reference("product_id", "products"),
        CheckConstraint(
            "quantity >= 0 AND reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="valid_quantities",
        ),
        {
            "schema": "erp",
            "comment": "Inventory snapshot by product and warehouse; available=quantity-reserved.",
        },
    )
    product_id: Mapped[UUID] = mapped_column()
    warehouse: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, server_default="0")
    reserved_quantity: Mapped[Decimal] = mapped_column(QUANTITY, server_default="0")
    product: Mapped["Product"] = relationship(back_populates="stock", viewonly=True)
