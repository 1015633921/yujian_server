from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from .community_ugc_models import (
    CommunityCommentCreate,
    CommunityPostCreate,
    CommunityPostUpdate,
    CommunityReportCreate,
)
from .community_ugc_service import (
    CommunityConflict,
    CommunityNotFound,
    CommunityValidation,
    community_ugc_service,
)
from .feature_flags import (
    community_moderation_required,
    community_ugc_enabled,
    community_ugc_writes_enabled,
)
from .user_sessions import UserPrincipal, require_current_user


community_ugc_router = APIRouter(prefix="/api/v1/community", tags=["灵感社区 UGC"])
CommunityResourceId = Annotated[str, Path(min_length=1, max_length=80)]
CommunityUserId = Annotated[str, Path(min_length=1, max_length=100)]


def success(data, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def require_community_read() -> None:
    if not community_ugc_enabled():
        raise HTTPException(status_code=503, detail="灵感社区 UGC 当前未开放")
    if not community_ugc_service.readiness()["schema_ready"]:
        raise HTTPException(status_code=503, detail="灵感社区 UGC 数据库迁移尚未就绪")


def require_community_write() -> None:
    require_community_read()
    if not community_ugc_writes_enabled():
        raise HTTPException(status_code=503, detail="灵感社区 UGC 写入当前未开放")


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CommunityNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CommunityConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@community_ugc_router.get("/readiness", summary="UGC 功能与迁移就绪状态")
def community_readiness():
    schema = community_ugc_service.readiness()
    read_enabled = community_ugc_enabled()
    write_enabled = community_ugc_writes_enabled()
    return success(
        {
            **schema,
            "read_enabled": read_enabled,
            "write_enabled": write_enabled,
            "moderation_required": community_moderation_required(),
            "read_available": read_enabled and bool(schema["schema_ready"]),
            "write_available": read_enabled and write_enabled and bool(schema["schema_ready"]),
        }
    )


@community_ugc_router.get("/posts", summary="公开的用户灵感列表")
def public_posts(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10000),
    _feature: None = Depends(require_community_read),
):
    return success(community_ugc_service.list_public_posts(limit=limit, offset=offset))


@community_ugc_router.get("/me/posts", summary="我的灵感帖子")
def my_posts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    _feature: None = Depends(require_community_read),
    principal: UserPrincipal = Depends(require_current_user),
):
    return success(
        community_ugc_service.list_owned_posts(principal.user_id, limit=limit, offset=offset)
    )


@community_ugc_router.get("/me/posts/{post_id}", summary="我的灵感帖子详情")
def my_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_read),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(community_ugc_service.get_owned_post(post_id, principal.user_id))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.get("/me/saved-posts", summary="我收藏的用户灵感")
def my_saved_posts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    _feature: None = Depends(require_community_read),
    principal: UserPrincipal = Depends(require_current_user),
):
    return success(
        community_ugc_service.list_saved_posts(principal.user_id, limit=limit, offset=offset)
    )


@community_ugc_router.get("/me/following", summary="我关注的社区用户")
def my_following(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    _feature: None = Depends(require_community_read),
    principal: UserPrincipal = Depends(require_current_user),
):
    return success(
        community_ugc_service.list_following(principal.user_id, limit=limit, offset=offset)
    )


@community_ugc_router.get("/posts/{post_id}", summary="公开的用户灵感详情")
def public_post(post_id: CommunityResourceId, _feature: None = Depends(require_community_read)):
    try:
        return success(community_ugc_service.get_public_post(post_id))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.post(
    "/posts", status_code=status.HTTP_201_CREATED, summary="创建用户灵感草稿"
)
def create_post(
    payload: CommunityPostCreate,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(
            community_ugc_service.create_post(
                principal.user_id, payload.model_dump(mode="json")
            ),
            "草稿已创建",
        )
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.patch("/posts/{post_id}", summary="编辑自己的灵感草稿")
def update_post(
    post_id: CommunityResourceId,
    payload: CommunityPostUpdate,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(
            community_ugc_service.update_post(
                post_id,
                principal.user_id,
                payload.model_dump(mode="json", exclude_unset=True),
            ),
            "草稿已保存",
        )
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.delete("/posts/{post_id}", summary="删除自己的灵感帖子")
def delete_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(
            community_ugc_service.delete_post(post_id, principal.user_id), "帖子已删除"
        )
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.post("/posts/{post_id}/submit", summary="提交灵感帖子审核")
def submit_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        result = community_ugc_service.submit_post(post_id, principal.user_id)
        message = "帖子已发布" if result["status"] == "published" else "帖子已提交审核"
        return success(result, message)
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.post("/posts/{post_id}/withdraw", summary="撤回自己的灵感帖子")
def withdraw_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(
            community_ugc_service.withdraw_post(post_id, principal.user_id), "帖子已撤回"
        )
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.put("/posts/{post_id}/like", summary="点赞用户灵感")
def like_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(community_ugc_service.set_like(post_id, principal.user_id, True))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.delete("/posts/{post_id}/like", summary="取消点赞用户灵感")
def unlike_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(community_ugc_service.set_like(post_id, principal.user_id, False))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.put("/posts/{post_id}/save", summary="收藏用户灵感")
def save_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(community_ugc_service.set_save(post_id, principal.user_id, True))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.delete("/posts/{post_id}/save", summary="取消收藏用户灵感")
def unsave_post(
    post_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(community_ugc_service.set_save(post_id, principal.user_id, False))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.get("/posts/{post_id}/comments", summary="用户灵感评论列表")
def comments(
    post_id: CommunityResourceId,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    _feature: None = Depends(require_community_read),
):
    try:
        return success(community_ugc_service.list_comments(post_id, limit=limit, offset=offset))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.post(
    "/posts/{post_id}/comments",
    status_code=status.HTTP_201_CREATED,
    summary="评论用户灵感",
)
def create_comment(
    post_id: CommunityResourceId,
    payload: CommunityCommentCreate,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(
            community_ugc_service.create_comment(post_id, principal.user_id, payload.content),
            "评论已发布",
        )
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.delete("/comments/{comment_id}", summary="删除自己的评论")
def delete_comment(
    comment_id: CommunityResourceId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(
            community_ugc_service.delete_comment(comment_id, principal.user_id), "评论已删除"
        )
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.put("/users/{user_id}/follow", summary="关注社区用户")
def follow_user(
    user_id: CommunityUserId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(community_ugc_service.set_follow(user_id, principal.user_id, True))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.delete("/users/{user_id}/follow", summary="取消关注社区用户")
def unfollow_user(
    user_id: CommunityUserId,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(community_ugc_service.set_follow(user_id, principal.user_id, False))
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc


@community_ugc_router.post(
    "/reports", status_code=status.HTTP_201_CREATED, summary="举报用户帖子或评论"
)
def create_report(
    payload: CommunityReportCreate,
    _feature: None = Depends(require_community_write),
    principal: UserPrincipal = Depends(require_current_user),
):
    try:
        return success(
            community_ugc_service.create_report(
                principal.user_id, payload.model_dump(mode="json")
            ),
            "举报已记录",
        )
    except (CommunityNotFound, CommunityConflict, CommunityValidation) as exc:
        raise translate_error(exc) from exc
