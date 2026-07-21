#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENT="${ENVIRONMENT:?set ENVIRONMENT to test or prod}"

echo "delegating to the unified Docker blue-green deployer" >&2
exec python3 "${ROOT}/scripts/deploy.py" "${ENVIRONMENT}"
