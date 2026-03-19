# See https://docs.astral.sh/uv/guides/integration/docker/
FROM ghcr.io/astral-sh/uv:alpine

WORKDIR /app
ENV UV_NO_DEV=1
COPY uv.lock pyproject.toml ./
RUN uv sync --locked
COPY app/ app/
# See https://fastapi.tiangolo.com/deployment/docker/?h=uv
CMD [ "uv", "run", "fastapi", "run", "app/main.py", "--proxy-headers",  "--port", "80" ]
