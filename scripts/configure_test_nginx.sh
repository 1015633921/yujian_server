#!/usr/bin/env bash
set -euo pipefail

CONFIG="/etc/nginx/conf.d/yujian-api.conf"

if ! grep -q "location /test-api/" "${CONFIG}"; then
  cp "${CONFIG}" "${CONFIG}.before_test_api_20260623"
  python3 - "${CONFIG}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = "    location / {\n"
block = """    location /test-api/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

"""
if marker not in text:
    raise SystemExit("production location block not found")
path.write_text(text.replace(marker, block + marker, 1))
PY
fi

nginx -t
systemctl reload nginx
