"""
Vertex Construction & PCCC - FastAPI Main Application
Autonomous AI Agent & Tools Pipeline for Fire Protection & MEP Quotations.
Includes Master Template Management, Pricing Coefficients, Rate Limiting, and Security Headers.
"""
import time
import os
import sys
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, status, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.config import settings
from app.database.db import db
from app.database.models import User
from app.services.auth import get_current_user_optional
from app.middlewares.rate_limiter import RateLimiterMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware
from app.routers import (
    auth_router, quotes_router, zalo_router, catalog_router,
    templates_router, cad_takeoff_router, field_reports_router,
    inventory_router, quote_builder_router
)
from app.tools.template_generator import create_master_template_excel

_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure storage folders and DB are initialized
    settings.setup_directories()
    db._seed_catalog()
    db._seed_users()
    db._seed_master_template()
    db._seed_inventory_data()

    # Generate master template excel if missing
    tpl_dir = Path(settings.STORAGE_DIR) / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    master_file = tpl_dir / "Master_Template_Vertex.xlsx"
    if not master_file.exists():
        create_master_template_excel(str(master_file))

    # Security check on startup
    if settings.APP_ENV == "production":
        if settings.SECRET_KEY == "vertex-secret-key-change-in-production":
            raise RuntimeError("[SECURITY ERROR] Không thể khởi chạy Production khi đang sử dụng SECRET_KEY mặc định! Vui lòng cấu hình SECRET_KEY an toàn trong .env.")
        if not settings.AI_API_KEY or settings.AI_API_KEY.strip() == "":
            raise RuntimeError("[SECURITY ERROR] Không thể khởi chạy Production khi AI_API_KEY bị bỏ trống! Vui lòng cấu hình AI_API_KEY trong .env.")

    print(f"[VERTEX] System started successfully on {settings.HOST}:{settings.PORT}")
    print(f"[VERTEX] Dashboard: {settings.BASE_URL}")
    print(f"[VERTEX] Login Page: {settings.BASE_URL}/login")
    print(f"[VERTEX] Swagger Docs: {settings.BASE_URL}/docs")
    print(f"[VERTEX] Healthcheck: {settings.BASE_URL}/api/health")
    yield
    # Shutdown
    print("[VERTEX] System shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Hệ thống tự động hóa báo giá thiết bị PCCC & vật tư cơ điện Vertex bằng AI Agent & FastAPI",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 1. Security Headers Middleware (OWASP protection)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Rate Limiting Middleware (Anti-DDoS & Brute-force protection)
app.add_middleware(RateLimiterMiddleware)

# 3. CORS Middleware
cors_origins = [settings.BASE_URL.rstrip("/")] if settings.APP_ENV == "production" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"] if settings.APP_ENV == "production" else ["*"],
    allow_headers=["*"],
)

# Ensure directories exist
for path in ["app/static", "app/static/css", "app/static/js", "app/templates", "storage/uploads", "storage/quotes", "storage/templates"]:
    Path(path).mkdir(parents=True, exist_ok=True)

# Mount Static Files & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Include API Routers
app.include_router(auth_router)
app.include_router(quotes_router)
app.include_router(zalo_router)
app.include_router(catalog_router)
app.include_router(templates_router)
app.include_router(cad_takeoff_router)
app.include_router(field_reports_router)
app.include_router(inventory_router)
app.include_router(quote_builder_router)

# Ensure all API 404 / 500 / Validation errors return valid JSON (avoids client syntax errors)
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail or "Not Found"}
    )

@app.exception_handler(Exception)
async def custom_general_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Lỗi hệ thống: {str(exc)}"}
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"}
    )

@app.get("/api/health")
@app.get("/health")
@app.get("/healthz")
async def health_check():
    """
    Returns application health status, database connectivity, and uptime.
    Used by Render, Docker healthchecks, Kubernetes probes, and Uptime monitors.
    """
    uptime_seconds = int(time.time() - _START_TIME)
    
    # Verify DB connectivity
    db_status = "healthy"
    total_quotes = 0
    total_catalog = 0
    try:
        total_quotes = db.count_quotes()
        total_catalog = len(db.get_catalog())
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "2.0.0",
        "uptime_seconds": uptime_seconds,
        "database": {
            "status": db_status,
            "total_quotes": total_quotes,
            "catalog_items": total_catalog
        },
        "ai_provider": {
            "name": settings.AI_PROVIDER,
            "model": settings.AI_MODEL_NAME,
            "base_url": settings.AI_BASE_URL
        }
    }


@app.get("/api/sample-files/{file_type}")
def get_sample_file_direct(file_type: str):
    from app.routers.quotes import get_sample_file
    return get_sample_file(file_type)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Main Dashboard View.
    Enforces authentication: Redirects unauthenticated users to /login.
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    quotes = db.list_quotes(limit=50)
    catalog = db.get_catalog()
    active_template = db.get_active_template()
    templates_list = db.list_templates()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "settings": settings,
            "user": current_user,
            "quotes": quotes,
            "catalog": catalog,
            "active_template": active_template,
            "templates_list": templates_list,
            "total_quotes": db.count_quotes()
        }
    )


@app.get("/cad-takeoff", response_class=HTMLResponse)
async def serve_cad_takeoff_direct(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Dedicated Standalone CAD/Revit Takeoff Page.
    Enforces authentication: Redirects unauthenticated users to /login.
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    active_template = db.get_active_template()
    return templates.TemplateResponse(
        request=request,
        name="cad_takeoff.html",
        context={
            "request": request,
            "settings": settings,
            "user": current_user,
            "active_template": active_template
        }
    )


@app.get("/field-reports", response_class=HTMLResponse)
async def serve_field_reports_direct(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Dedicated Field Reports & GPS Attendance Management Page.
    Enforces authentication: Redirects unauthenticated users to /login.
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    checkins = db.list_checkins(limit=50)
    reports = db.list_field_reports(limit=50)
    from app.routers.field_reports import PROJECT_SITES

    return templates.TemplateResponse(
        request=request,
        name="field_reports.html",
        context={
            "request": request,
            "settings": settings,
            "user": current_user,
            "checkins": checkins,
            "reports": reports,
            "project_sites": PROJECT_SITES
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
