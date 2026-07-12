#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RELEASE_VERSION="${RELEASE_VERSION:?set RELEASE_VERSION, for example v20260712-001}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:?set IMAGE_REPOSITORY without a tag}"
VCS_REF="${VCS_REF:-$(git -C "${ROOT}" rev-parse HEAD)}"
MODE="${1:---load}"

if [[ ! "${RELEASE_VERSION}" =~ ^v[0-9]{8}-[0-9]{3}(-[a-z0-9.-]+)?$ ]]; then
  echo "invalid RELEASE_VERSION" >&2
  exit 1
fi
if [[ "${IMAGE_REPOSITORY}" == *:latest || "${IMAGE_REPOSITORY}" == *@* ]]; then
  echo "IMAGE_REPOSITORY must not contain latest or a digest" >&2
  exit 1
fi
if [[ "${MODE}" != "--load" && "${MODE}" != "--push" ]]; then
  echo "usage: build_image.sh [--load|--push]" >&2
  exit 1
fi

IMAGE_TAG="${IMAGE_REPOSITORY}:${RELEASE_VERSION}"
METADATA_FILE="$(mktemp)"
trap 'rm -f "${METADATA_FILE}"' EXIT

docker buildx build "${ROOT}" \
  --file "${ROOT}/Dockerfile" \
  --platform "${TARGET_PLATFORM:-linux/amd64}" \
  --tag "${IMAGE_TAG}" \
  --build-arg "RELEASE_VERSION=${RELEASE_VERSION}" \
  --build-arg "VCS_REF=${VCS_REF}" \
  --provenance=mode=max \
  --sbom=true \
  --metadata-file "${METADATA_FILE}" \
  "${MODE}"

echo "built ${IMAGE_TAG} from ${VCS_REF}"
if [[ "${MODE}" == "--push" ]]; then
  python3 - "${METADATA_FILE}" "${IMAGE_REPOSITORY}" <<'PY'
import json
import sys

metadata = json.load(open(sys.argv[1], encoding="utf-8"))
digest = metadata.get("containerimage.digest")
if not digest:
    raise SystemExit("registry digest missing from build metadata")
print(f"immutable image: {sys.argv[2]}@{digest}")
PY
fi
