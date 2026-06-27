from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import threading
import time

from .admin_api import admin_router
from .admin_page import admin_page
from .api import legacy_router, order_service, router

app = FastAPI(
    title="宇涧水晶 DIY API",
    description="专属水晶测算、五行能量画像与手串定制推荐服务",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(legacy_router)
app.include_router(admin_router)


@app.middleware("http")
async def admin_static_cache_control(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/admin":
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


def logistics_sync_loop() -> None:
    interval = max(300, int(os.getenv("LOGISTICS_SYNC_INTERVAL_SECONDS", "1800")))
    while True:
        time.sleep(interval)
        try:
            order_service.refresh_active_shipments()
        except Exception:
            # 单次第三方物流异常不能影响主服务，下一轮会继续重试。
            continue


@app.on_event("startup")
def start_logistics_sync() -> None:
    if str(os.getenv("LOGISTICS_SYNC_ENABLED", "true")).lower() not in {"1", "true", "yes", "on"}:
        return
    worker = threading.Thread(target=logistics_sync_loop, name="logistics-sync", daemon=True)
    worker.start()


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
        },
    }


@app.get("/admin", tags=["后台管理"], include_in_schema=False)
def admin():
    return admin_page()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数校验失败",
            "data": {"errors": jsonable_encoder(exc.errors())},
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务内部错误", "data": None},
    )
