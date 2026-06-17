from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .admin_service import AdminService

admin_router = APIRouter(prefix="/api/v1/admin", tags=["后台管理"])
admin_service = AdminService()


class AdminAuthPayload(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=80)


class MaterialPayload(BaseModel):
    id: str | None = None
    skuId: str
    top: str
    category: str
    series: str | None = ""
    grade: str | None = ""
    name: str
    effect: str
    element: str
    price: float = 0
    size: float = 8
    weight: float = 1
    color: str = "#dfe3e5"
    shine: str = "#ffffff"
    image_path: str | None = ""
    image_url: str | None = ""
    enabled: bool = True
    sort_order: int = 0


class ContentBlockPayload(BaseModel):
    block_id: str | None = None
    section: str = "home"
    title: str
    subtitle: str | None = ""
    body: str | None = ""
    image_url: str | None = ""
    action_text: str | None = ""
    action_url: str | None = ""
    status: str = "draft"
    sort_order: int = 0


def success(data, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def token_from_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def require_admin(authorization: str | None) -> dict:
    try:
        return admin_service.require_admin(token_from_header(authorization))
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@admin_router.post("/register", summary="注册后台管理员")
def register_admin(payload: AdminAuthPayload):
    try:
        result = admin_service.register(payload.username, payload.password)
        return success(result, "注册成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/login", summary="后台登录")
def login_admin(payload: AdminAuthPayload):
    try:
        return success(admin_service.login(payload.username, payload.password), "登录成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/me", summary="当前后台用户")
def admin_me(authorization: str | None = Header(default=None)):
    return success(require_admin(authorization))


@admin_router.get("/dashboard", summary="后台仪表盘")
def dashboard(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return success(admin_service.dashboard())


@admin_router.get("/users", summary="小程序用户列表")
def users(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_users(keyword=keyword, limit=limit))


@admin_router.get("/assessments", summary="测算记录列表")
def assessments(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_assessments(keyword=keyword, limit=limit))


@admin_router.get("/daily-energies", summary="每日能量记录列表")
def daily_energies(
    keyword: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_daily_energies(keyword=keyword, limit=limit))


@admin_router.get("/materials", summary="后台材料列表")
def materials(
    keyword: str = Query(default="", max_length=80),
    top: str = Query(default="", max_length=40),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_materials(keyword=keyword, top=top))


@admin_router.post("/materials", summary="新增材料")
def create_material(payload: MaterialPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_material(payload.model_dump()), "材料已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/materials/{material_id}", summary="更新材料")
def update_material(material_id: str, payload: MaterialPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_material(payload.model_dump(), material_id=material_id), "材料已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/materials/{material_id}", summary="删除材料")
def delete_material(material_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    admin_service.delete_material(material_id)
    return success({"deleted": material_id}, "材料已删除")


@admin_router.get("/blocks", summary="板块内容列表")
def blocks(
    section: str = Query(default="", max_length=40),
    authorization: str | None = Header(default=None),
):
    require_admin(authorization)
    return success(admin_service.list_blocks(section=section))


@admin_router.post("/blocks", summary="新增板块内容")
def create_block(payload: ContentBlockPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_block(payload.model_dump()), "板块已保存")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.put("/blocks/{block_id}", summary="更新板块内容")
def update_block(block_id: str, payload: ContentBlockPayload, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    try:
        return success(admin_service.save_block(payload.model_dump(), block_id=block_id), "板块已更新")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.delete("/blocks/{block_id}", summary="删除板块内容")
def delete_block(block_id: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    admin_service.delete_block(block_id)
    return success({"deleted": block_id}, "板块已删除")
