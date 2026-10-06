"""Versioned route composition."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.connections import router as connections_router
from app.api.routes.health import router as health_router
from app.api.routes.nlq import router as nlq_router
from app.api.routes.workspace import router as workspace_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(connections_router, tags=["connections"])
api_router.include_router(nlq_router, tags=["nlq"])
api_router.include_router(workspace_router, tags=["workspace"])
