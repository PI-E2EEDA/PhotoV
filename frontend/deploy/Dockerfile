FROM fedora:43 AS frontendbuild
RUN dnf install -y git wget pnpm
WORKDIR /frontend
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /frontend/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
COPY . /frontend
RUN pnpm build

# Take /frontend/web/dist as the final useful folder for the web interface
FROM caddy:2.8-alpine
# Copy static files to default location of Caddy (/srv)
COPY --from=frontendbuild /frontend/dist /srv
# Copy config file of Caddy
COPY deploy/Caddyfile /etc/caddy/Caddyfile

WORKDIR /srv
EXPOSE 80
