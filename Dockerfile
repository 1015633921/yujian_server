FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -i https://mirrors.cloud.tencent.com/pypi/simple --upgrade pip \
    && pip install -i https://mirrors.cloud.tencent.com/pypi/simple -r requirements.txt

COPY app ./app
COPY static ./static

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
