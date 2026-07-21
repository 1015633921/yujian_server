#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENT="${ENVIRONMENT:?set ENVIRONMENT to test or prod}"

exec python3 "${ROOT}/scripts/deploy.py" "${ENVIRONMENT}" rollback
