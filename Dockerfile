FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.lock pyproject.toml README.md alembic.ini ./

RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.lock && \
    python -m playwright install --with-deps chromium && \
    useradd --create-home --uid 10001 radar && \
    mkdir -p /data && \
    chown -R radar:radar /app /data /ms-playwright

COPY --chown=radar:radar app ./app
COPY --chown=radar:radar alembic ./alembic
COPY --chown=radar:radar docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod 755 /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
