from __future__ import annotations

import os
import tempfile
from pathlib import Path


TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="yujian-p0a-tests-"))
TEST_DATABASE_PATH = TEST_DATA_DIR / "test.db"

os.environ["SQLITE_DATABASE_PATH"] = str(TEST_DATABASE_PATH)
os.environ["DATABASE_BACKEND"] = "sqlite"
os.environ.setdefault("COMMERCE_CHECKOUT_ENABLED", "false")
os.environ.setdefault("WECHAT_PAYMENT_ENABLED", "false")
os.environ.setdefault("REPORT_VERSIONING_V2_ENABLED", "false")
os.environ.setdefault("DIY_PUBLIC_SHARE_ENABLED", "false")
os.environ.setdefault("REMOTE_AVATAR_FETCH_ENABLED", "false")
os.environ.setdefault("LOGISTICS_SYNC_ENABLED", "false")
os.environ.setdefault("KUAIDI100_SUBSCRIBE_ENABLED", "false")
os.environ.setdefault("METRICS_ENDPOINT_ENABLED", "false")
os.environ.setdefault("ALLOW_DEV_WECHAT_LOGIN", "true")
os.environ.setdefault("TRUST_CLOUDBASE_IDENTITY_HEADERS", "false")

from app.order_service import OrderService  # noqa: E402
from app.repository import AssessmentRepository  # noqa: E402
from app.admin_service import AdminService  # noqa: E402
from app.migrations.runner import upgrade  # noqa: E402


AssessmentRepository(TEST_DATABASE_PATH)
OrderService(TEST_DATABASE_PATH)
AdminService(TEST_DATABASE_PATH)
upgrade("sqlite", TEST_DATABASE_PATH)
