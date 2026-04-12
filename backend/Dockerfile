# See https://docs.astral.sh/uv/guides/integration/docker/
FROM ghcr.io/astral-sh/uv:alpine

WORKDIR /app
ENV UV_NO_DEV=1
COPY uv.lock pyproject.toml ./
RUN uv sync --locked
ADD "https://api.github.com/repos/PI-E2EEDA/PhotoV/commits?per_page=1" latest_commit
COPY . .
# See https://fastapi.tiangolo.com/deployment/docker/?h=uv
CMD [ "uv", "run", "fastapi", "run", "app/main.py", "--proxy-headers",  "--port", "80" ]
