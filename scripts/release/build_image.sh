#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RELEASE_VERSION="${RELEASE_VERSION:?set RELEASE_VERSION, for example v20260712-001}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:?set IMAGE_REPOSITORY without a tag}"
BUILD_CONTEXT_HASH="${BUILD_CONTEXT_HASH:?set BUILD_CONTEXT_HASH to the backend build-context sha256}"
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

build_args=(
  --file "${ROOT}/Dockerfile"
  --platform "${TARGET_PLATFORM:-linux/amd64}"
  --tag "${IMAGE_TAG}"
  --build-arg "BUILD_CONTEXT_HASH=${BUILD_CONTEXT_HASH}"
  --provenance=false
  --sbom=false
  --metadata-file "${METADATA_FILE}"
)
if [[ -n "${BUILD_CACHE_FROM:-}" ]]; then
  build_args+=(--cache-from "${BUILD_CACHE_FROM}")
fi
if [[ -n "${BUILD_CACHE_TO:-}" ]]; then
  build_args+=(--cache-to "${BUILD_CACHE_TO}")
fi
build_args+=("${MODE}" "${ROOT}")

docker buildx build "${build_args[@]}"

echo "built ${IMAGE_TAG} from backend context ${BUILD_CONTEXT_HASH}"
if [[ "${MODE}" == "--push" ]]; then
  immutable_image="$(python3 - "${METADATA_FILE}" "${IMAGE_REPOSITORY}" <<'PY'
import json
import sys

metadata = json.load(open(sys.argv[1], encoding="utf-8"))
digest = metadata.get("containerimage.digest")
if not digest:
    raise SystemExit("registry digest missing from build metadata")
print(f"immutable image: {sys.argv[2]}@{digest}")
PY
)"
  echo "${immutable_image}"
  if [[ -n "${IMAGE_REF_FILE:-}" ]]; then
    umask 077
    printf '%s\n' "${immutable_image#immutable image: }" > "${IMAGE_REF_FILE}"
  fi
fi
