"""
Routers Package for Vertex Quote Automation
"""
from app.routers.auth import router as auth_router
from app.routers.quotes import router as quotes_router
from app.routers.zalo_webhook import router as zalo_router
from app.routers.catalog import router as catalog_router
from app.routers.templates import router as templates_router
from app.routers.cad_takeoff import router as cad_takeoff_router
from app.routers.field_reports import router as field_reports_router
from app.routers.inventory import router as inventory_router
from app.routers.quote_builder import router as quote_builder_router

__all__ = [
    "auth_router", "quotes_router", "zalo_router", "catalog_router",
    "templates_router", "cad_takeoff_router", "field_reports_router",
    "inventory_router", "quote_builder_router"
]


