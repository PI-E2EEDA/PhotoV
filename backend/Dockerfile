# See https://docs.astral.sh/uv/guides/integration/docker/
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_NO_DEV=1

# Installation de libgomp1 pour LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY uv.lock pyproject.toml ./
RUN uv sync --locked

# Alembic needs these files inside the container
COPY alembic.ini ./
COPY migrations/ migrations/
COPY app/ app/

# See https://fastapi.tiangolo.com/deployment/docker/?h=uv
CMD [ "uv", "run", "fastapi", "run", "app/main.py", "--proxy-headers", "--port", "80" ]
