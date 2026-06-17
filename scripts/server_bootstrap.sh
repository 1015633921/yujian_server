#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y docker-ce docker-ce-cli docker-compose-plugin docker-buildx-plugin
  else
    curl -fsSL https://get.docker.com | sh
  fi
fi

systemctl enable --now docker
mkdir -p /opt/yujian/data
cd /opt/yujian
docker compose up -d --build
docker compose ps
