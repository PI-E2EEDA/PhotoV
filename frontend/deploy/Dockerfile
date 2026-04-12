FROM fedora:43 AS frontendbuild
RUN dnf install -y git wget pnpm
ADD "https://api.github.com/repos/PI-E2EEDA/PhotoV/commits?per_page=1" latest_commit
WORKDIR /frontend
COPY . /frontend
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
RUN pnpm build

# Take /frontend/web/dist as the final useful folder for the web interface
FROM caddy:2.8-alpine
# Copy static files to default location of Caddy (/srv)
COPY --from=frontendbuild /frontend/dist /srv
# Copy config file of Caddy
COPY deploy/Caddyfile /etc/caddy/Caddyfile

WORKDIR /srv
EXPOSE 80
