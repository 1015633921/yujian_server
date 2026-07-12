#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENT="${ENVIRONMENT:?set ENVIRONMENT to test or prod}"
ENV_FILE="${ENV_FILE:?set ENV_FILE to the runtime environment file}"
APP_IMAGE="${APP_IMAGE:?set APP_IMAGE to repository@sha256:digest}"

python3 "${ROOT}/scripts/validate_release_env.py" --environment "${ENVIRONMENT}" --env-file "${ENV_FILE}"
python3 "${ROOT}/scripts/validate_image_ref.py" "${APP_IMAGE}"
python3 "${ROOT}/scripts/scan_secrets.py"
python3 "${ROOT}/scripts/check_repository.py"
python3 "${ROOT}/scripts/check_migrations.py" --backend sqlite
git -C "${ROOT}" diff --check

echo "release preflight passed; production was not contacted"
