FROM ghcr.io/astral-sh/uv:alpine

WORKDIR /app
ENV UV_NO_DEV=1
COPY uv.lock pyproject.toml ./
RUN uv sync --locked
COPY app .
CMD [ "uv", "run", "fastapi", "run", "--proxy-headers", "app/main.py", "--port", "80" ]
