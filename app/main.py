from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .admin_api import admin_router
from .admin_page import admin_page
from .api import legacy_router, router

app = FastAPI(
    title="遇见水晶 DIY API",
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


@app.get("/", tags=["system"])
def root():
    return health()


@app.get("/health", tags=["系统"])
def health():
    return {"code": 0, "message": "ok", "data": {"service": "yujian-fastapi", "version": "2.0.0"}}


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
