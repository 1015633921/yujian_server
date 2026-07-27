FROM python:3.12.13-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b

ARG RELEASE_VERSION=dev
ARG VCS_REF=unknown
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock .
RUN python -m pip install --index-url "$PIP_INDEX_URL" --require-hashes -r requirements.lock

COPY app ./app
COPY static ./static
COPY scripts/migrate_sqlite_to_mysql.py ./scripts/migrate_sqlite_to_mysql.py
COPY scripts/regenerate_material_skus_and_knowledge.py ./scripts/regenerate_material_skus_and_knowledge.py

RUN groupadd --system --gid 10001 yujian \
    && useradd --system --uid 10001 --gid yujian --home-dir /app yujian \
    && mkdir -p /app/data \
    && chown -R yujian:yujian /app

LABEL org.opencontainers.image.title="yujian-api" \
      org.opencontainers.image.version="${RELEASE_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
