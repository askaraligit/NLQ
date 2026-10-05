"""Complete metadata registration for migrations and offline schema inspection."""

from app.models.application import (
    AnalyticsPrincipal,
    Conversation,
    QueryRecord,
    SavedQuery,
    SeedRun,
    Tenant,
    User,
    UserSettings,
)
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
    "Conversation",
    "Base",
    "Customer",
    "Payment",
    "Product",
    "ProductCategory",
    "PurchaseInvoice",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "QueryRecord",
    "SavedQuery",
    "SalesInvoice",
    "SalesOrder",
    "SalesOrderItem",
    "SeedRun",
    "Stock",
    "Supplier",
    "Tenant",
    "User",
    "UserSettings",
]
