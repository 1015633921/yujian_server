from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from fastapi.responses import HTMLResponse


ADMIN_HTML_PATH = Path(__file__).resolve().parent.parent / "static" / "admin" / "index.html"
ADMIN_STATIC_DIR = ADMIN_HTML_PATH.parent


def admin_asset_version() -> str:
    configured = os.getenv("ADMIN_ASSET_VERSION", "").strip()
    if configured:
        return configured

    digest = hashlib.sha256()
    for filename in ("index.html", "admin.css", "admin.js"):
        path = ADMIN_STATIC_DIR / filename
        if path.exists():
            digest.update(filename.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def inject_admin_asset_version(html: str, version: str) -> str:
    html = re.sub(
        r'(href=["\']static/admin/admin\.css)(?:\?v=[^"\']*)?(["\'])',
        rf"\1?v={version}\2",
        html,
    )
    html = re.sub(
        r'(src=["\']static/admin/admin\.js)(?:\?v=[^"\']*)?(["\'])',
        rf"\1?v={version}\2",
        html,
    )
    return html


def admin_page() -> HTMLResponse:
    version = admin_asset_version()
    return HTMLResponse(
        inject_admin_asset_version(ADMIN_HTML_PATH.read_text(encoding="utf-8"), version),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Admin-Asset-Version": version,
        },
    )
