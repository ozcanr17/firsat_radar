FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.lock pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY alembic ./alembic

RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.lock && \
    python -m pip install --no-deps . && \
    python -m playwright install --with-deps chromium && \
    useradd --create-home --uid 10001 radar && \
    mkdir -p /data && \
    chown -R radar:radar /app /data /ms-playwright

USER radar

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
