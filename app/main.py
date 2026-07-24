from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path
import hmac
import logging
import os

from .runtime_health import assert_startup_configuration, readiness

assert_startup_configuration()

from .admin_api import admin_router  # noqa: E402
from .ai_material_api import ai_material_router  # noqa: E402
from .admin_page import admin_page  # noqa: E402
from .api import legacy_router, router  # noqa: E402
from .web_login_pairing import web_login_pairing_router  # noqa: E402
from .observability import (
    REQUEST_ID_HEADER,
    Timer,
    bind_request_id,
    bind_user_id,
    configure_logging,
    current_request_id,
    log_event,
    metrics,
    normalize_request_id,
    reset_request_id,
    reset_user_id,
    safe_exception_frames,
)
from .feature_flags import metrics_endpoint_enabled

configure_logging()
LOGGER = logging.getLogger("yujian.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    assert_startup_configuration()
    yield


app = FastAPI(
    title="宇涧水晶 DIY API",
    description="专属水晶分析、五行元素画像与手串定制推荐服务",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)

app.include_router(router)
app.include_router(legacy_router)
app.include_router(admin_router)
app.include_router(ai_material_router)
app.include_router(web_login_pairing_router)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
    request_token = bind_request_id(request_id)
    user_token = bind_user_id(None)
    request.state.request_id = request_id
    timer = Timer()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    except Exception as exc:
        log_event(
            LOGGER,
            "api.request.unhandled",
            level=logging.ERROR,
            route=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
            stack=safe_exception_frames(exc),
            result="failed",
        )
        response = JSONResponse(
            status_code=500,
            headers={REQUEST_ID_HEADER: request_id},
            content={
                "code": "INTERNAL_ERROR",
                "message": "服务内部错误",
                "request_id": request_id,
                "data": None,
            },
        )
        return response
    finally:
        route_object = request.scope.get("route")
        route = getattr(route_object, "path", None) or "unmatched"
        status_class = f"{max(1, status_code // 100)}xx"
        metrics.increment("api_request_total", method=request.method, route=route, status_class=status_class)
        metrics.observe("api_latency", timer.elapsed_ms, method=request.method, route=route)
        if status_code >= 400:
            metrics.increment("api_error_total", method=request.method, route=route, status_class=status_class)
        log_event(
            LOGGER,
            "api.request.completed",
            route=route,
            method=request.method,
            duration_ms=timer.elapsed_ms,
            result="success" if status_code < 400 else "failed",
            status_code=status_code,
        )
        reset_user_id(user_token)
        reset_request_id(request_token)


@app.middleware("http")
async def admin_static_cache_control(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json") and "charset=" not in content_type.lower():
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    path = request.url.path
    if request.headers.get("authorization") or request.url.path.startswith("/api/v1/auth/web-pairings"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    elif path == "/admin":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    elif path.startswith("/static/admin/"):
        if "v=" in request.url.query:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", tags=["system"])
def root():
    return health()


@app.get("/health", tags=["系统"])
def health():
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "service": "yujian-fastapi",
            "version": "2.0.0",
            "environment": os.getenv("APP_ENV", "development"),
            "database": os.getenv("DATABASE_BACKEND", "sqlite"),
            "status": "alive",
        },
    }


@app.get("/health/live", tags=["系统"])
def health_live():
    return {
        "code": 0,
        "message": "alive",
        "data": {"service": "yujian-fastapi", "status": "alive"},
    }


@app.get("/health/ready", tags=["系统"])
def health_ready():
    result = readiness()
    content = {
        "code": 0 if result["ready"] else "SERVICE_NOT_READY",
        "message": "ready" if result["ready"] else "service not ready",
        "data": result,
    }
    if result["ready"]:
        return content
    return JSONResponse(status_code=503, content=content)


@app.get("/internal/metrics", tags=["系统"], include_in_schema=False)
def internal_metrics(authorization: str | None = Header(default=None)):
    if not metrics_endpoint_enabled():
        raise HTTPException(status_code=404, detail="资源不存在")
    expected = os.getenv("METRICS_ACCESS_TOKEN", "")
    supplied = str(authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="指标端点配置不完整")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="未授权")
    return {"code": 0, "message": "ok", "data": metrics.snapshot()}


@app.get("/admin", tags=["后台管理"], include_in_schema=False)
def admin():
    return admin_page()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"type": item.get("type"), "loc": list(item.get("loc") or []), "msg": item.get("msg")}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数校验失败",
            "request_id": current_request_id(),
            "data": {"errors": jsonable_encoder(errors)},
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code") or f"HTTP_{exc.status_code}"
        message = detail.get("message") or "请求失败"
    else:
        code = f"HTTP_{exc.status_code}"
        message = str(detail or "请求失败")
    if exc.status_code >= 500:
        message = "服务暂时不可用"
        detail = message
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "code": code,
            "message": message,
            "request_id": current_request_id(),
            "detail": detail,
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or current_request_id()
    log_event(
        LOGGER,
        "api.exception.unhandled",
        level=logging.ERROR,
        route=getattr(request.scope.get("route"), "path", request.url.path),
        method=request.method,
        request_id=request_id,
        error_type=type(exc).__name__,
        stack=safe_exception_frames(exc),
        result="failed",
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务内部错误",
            "request_id": request_id,
            "data": None,
        },
    )
