"""Complete metadata registration for migrations and offline schema inspection."""

from app.models.application import AnalyticsPrincipal, SeedRun, Tenant
from app.models.base import Base
from app.models.erp import (
    Customer,
    Payment,
    Product,
    ProductCategory,
    PurchaseInvoice,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesInvoice,
    SalesOrder,
    SalesOrderItem,
    Stock,
    Supplier,
)

__all__ = [
    "AnalyticsPrincipal",
    "Base",
    "Customer",
    "Payment",
    "Product",
    "ProductCategory",
    "PurchaseInvoice",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "SalesInvoice",
    "SalesOrder",
    "SalesOrderItem",
    "SeedRun",
    "Stock",
    "Supplier",
    "Tenant",
]
