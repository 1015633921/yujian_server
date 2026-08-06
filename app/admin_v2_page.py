from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse


ADMIN_V2_DIR = Path(__file__).resolve().parent.parent / "static" / "admin-v2"
DEDICATED_TEST_ADMIN_HOST = "operation-test.yustream.cn"


def admin_v2_asset_dir() -> Path:
    return ADMIN_V2_DIR / "assets"


def _request_host(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-host") or "").split(",", 1)[0]
    value = forwarded or str(request.headers.get("host") or "")
    return value.strip().split(":", 1)[0].lower()


def _base_path(path: str, host: str = "") -> str:
    if host == DEDICATED_TEST_ADMIN_HOST:
        return "/"
    marker = "/admin-v2"
    index = path.find(marker)
    prefix = path[:index] if index >= 0 else ""
    return f"{prefix}{marker}/"


def admin_v2_page(request: Request) -> HTMLResponse:
    """Serve the Vue SPA shell with a base path that survives test-prefix routing."""
    index_path = ADMIN_V2_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=503, detail="新版运营后台构建产物暂不可用")
    html = index_path.read_text(encoding="utf-8")
    base = escape(_base_path(request.url.path, _request_host(request)), quote=True)
    if "<head>" not in html:
        raise HTTPException(status_code=503, detail="新版运营后台入口文件无效")
    return HTMLResponse(
        html.replace("<head>", f'<head><base href="{base}">', 1),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
