FROM node:24.17.0-bookworm-slim@sha256:862263c612aa437e3037674b85419622a9d93bff80aa1eee5398dfe686375532 AS admin_web_build

WORKDIR /workspace/admin-web

COPY admin-web/package.json admin-web/package-lock.json ./
RUN npm ci

COPY admin-web ./
RUN npm run build


FROM python:3.12.13-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b

ARG BUILD_CONTEXT_HASH=unknown
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock .
RUN python -m pip install --index-url "$PIP_INDEX_URL" --require-hashes -r requirements.lock

COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 static ./static
COPY --from=admin_web_build --chown=10001:10001 /workspace/admin-web/dist ./static/admin-v2
COPY scripts/migrate_sqlite_to_mysql.py ./scripts/migrate_sqlite_to_mysql.py
COPY scripts/regenerate_material_skus_and_knowledge.py ./scripts/regenerate_material_skus_and_knowledge.py

RUN groupadd --system --gid 10001 yujian \
    && useradd --system --uid 10001 --gid yujian --home-dir /app yujian \
    && mkdir -p /app/data \
    && chown yujian:yujian /app /app/data /app/scripts \
    && chown yujian:yujian /app/scripts/*.py

LABEL org.opencontainers.image.title="yujian-api" \
      org.opencontainers.image.source-hash="${BUILD_CONTEXT_HASH}"

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
